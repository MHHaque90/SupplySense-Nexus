"""Phase 10 MILP formulation tests (spec section 25.C).

Covers configuration validation, declared objectives, variable/row
construction, determinism of the problem id, and the empty-scope path.
All data here is SYNTHETIC.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.analytics.optimization import (
    OBJECTIVES,
    OptimizationConfig,
)
from backend.app.analytics.optimization import inputs as inputs_mod
from backend.app.analytics.optimization import problem as problem_mod
from backend.app.tests.optimization_support import build_case, short_outage_scenario

FREEZING = [
    ("objective", "not_a_real_objective"),
    ("objective", "cost_shortage_tradeoff"),
    ("budget", -5.0),
    ("min_fulfillment", 1.5),
    ("quantity_integrality", "binary"),
]


def _inputs(**kwargs) -> inputs_mod.OptimizationInputs:
    case = build_case(short_outage_scenario())
    return inputs_mod.build_optimization_inputs(
        case["run"], case["entities"], case["inputs"]["supplier_links"], **kwargs,
    )


def _full_outage_inputs() -> inputs_mod.OptimizationInputs:
    case = build_case()
    return inputs_mod.build_optimization_inputs(
        case["run"], case["entities"], case["inputs"]["supplier_links"],
    )


@pytest.mark.parametrize(
    ("field", "value"),
    FREEZING,
    ids=[f"{field}={value}" for field, value in FREEZING],
)
def test_invalid_configuration_raises_value_error(field, value):
    config = OptimizationConfig(**{field: value})
    with pytest.raises(ValueError):
        problem_mod.build_formulation(_inputs(), config)


def test_unknown_objective_error_names_allowed_values():
    config = OptimizationConfig(objective="rank_suppliers")
    with pytest.raises(ValueError, match="minimize_total_cost"):
        problem_mod.build_formulation(_inputs(), config)


def test_each_declared_objective_has_expected_metadata():
    inputs = _inputs()
    expectations = {
        "minimize_total_cost": ("minimize", "currency_units"),
        "minimize_shortage": ("minimize", "demand_units"),
        "cost_shortage_tradeoff": ("minimize", "currency_units"),
        "maximize_service_fulfillment": ("maximize", "demand_units"),
    }
    for key, (direction, units) in expectations.items():
        config = OptimizationConfig(
            objective=key,
            shortage_penalty_per_unit=10.0 if key == "cost_shortage_tradeoff" else None,
        )
        formulation = problem_mod.build_formulation(inputs, config)
        objective = formulation.problem.objective
        assert objective.name == key
        assert objective.direction == direction
        assert objective.units == units
        assert objective.components
        assert objective.description


def test_objectives_tuple_matches_formulation_support():
    assert OBJECTIVES == (
        "minimize_total_cost",
        "minimize_shortage",
        "cost_shortage_tradeoff",
        "maximize_service_fulfillment",
    )


def test_problem_id_is_stable_and_config_scoped():
    inputs = _inputs()
    config_a = OptimizationConfig(objective="minimize_total_cost")
    config_b = OptimizationConfig(objective="minimize_shortage")
    first = problem_mod.build_formulation(inputs, config_a)
    second = problem_mod.build_formulation(inputs, config_a)
    other = problem_mod.build_formulation(inputs, config_b)
    assert first.problem.problem_id == second.problem.problem_id
    assert first.problem.problem_id != other.problem.problem_id
    assert first.problem.problem_id.startswith("OPT-")
    assert len(first.problem.problem_id) == len("OPT-") + 16


def test_decision_variables_expose_orders_only():
    formulation = problem_mod.build_formulation(_inputs())
    names = [item.name for item in formulation.problem.decision_variables]
    assert names
    assert all(name.startswith("order[") for name in names)
    assert not any(name.startswith("moq_used[") for name in names)
    auxiliary = formulation.problem.parameters["auxiliary_variables"]
    assert "moq_used" in auxiliary
    assert "excluded" in auxiliary


def test_order_variables_are_integer_by_default_and_continuous_on_request():
    inputs = _inputs()
    integer_formulation = problem_mod.build_formulation(inputs)
    assert all(
        item.integrality == "integer"
        for item in integer_formulation.problem.decision_variables
    )
    index = {
        name: position
        for position, name in enumerate(integer_formulation.variable_names)
    }
    for item in integer_formulation.problem.decision_variables:
        assert integer_formulation.integrality[index[item.name]] == 1
    continuous_formulation = problem_mod.build_formulation(
        inputs, OptimizationConfig(quantity_integrality="continuous"),
    )
    assert all(
        item.integrality == "continuous"
        for item in continuous_formulation.problem.decision_variables
    )


def test_demand_satisfaction_hard_only_for_cost_objective():
    inputs = _inputs()
    cost_formulation = problem_mod.build_formulation(
        inputs, OptimizationConfig(objective="minimize_total_cost"),
    )
    shortage_formulation = problem_mod.build_formulation(
        inputs, OptimizationConfig(objective="minimize_shortage"),
    )
    cost_rows = [row for row in cost_formulation.rows
                 if row.type == "demand_satisfaction"]
    shortage_rows = [row for row in shortage_formulation.rows
                     if row.type == "demand_satisfaction"]
    assert cost_rows
    assert not shortage_rows
    declared = {item.name: item for item in shortage_formulation.problem.constraints}
    assert declared["demand_satisfaction"].hard_or_soft == "soft"
    cost_declared = {
        item.name: item for item in cost_formulation.problem.constraints
    }
    assert cost_declared["demand_satisfaction"].hard_or_soft == "hard"
    assert cost_formulation.problem.parameters["demand_satisfaction_hard"] is True
    assert shortage_formulation.problem.parameters["demand_satisfaction_hard"] is False


def test_moq_rows_and_capacity_rows_follow_observed_links():
    inputs = _inputs()
    formulation = problem_mod.build_formulation(inputs)
    moq_rows = [row for row in formulation.rows
                if row.type == "minimum_order_quantity"]
    capacity_rows = [row for row in formulation.rows
                     if row.type == "supplier_capacity"]
    assert len(moq_rows) == 2 * len(formulation.problem.parameters["eligible_offers"])
    # S1 -> P1 carries a nullable capacity that is missing in the data.
    assert not any("S1" in row.name for row in capacity_rows)
    declared = {item.name for item in formulation.problem.constraints}
    assert not any(name.startswith("supplier_capacity:S1")
                   for name in declared)


def test_over_purchase_bound_equals_max_demand_and_moq():
    inputs = _inputs()
    formulation = problem_mod.build_formulation(inputs)
    bounds = formulation.problem.parameters["procurement_bounds"]
    assert set(bounds) == {"P1"}
    assert bounds["P1"] == pytest.approx(560.0)
    rows = [row for row in formulation.rows
            if row.type == "over_purchase_bound"]
    assert rows
    assert rows[0].upper == pytest.approx(560.0)


def test_budget_and_service_rows_only_when_configured():
    inputs = _inputs()
    plain = problem_mod.build_formulation(inputs)
    assert not [row for row in plain.rows if row.type == "budget"]
    assert not [row for row in plain.rows
                if row.type == "service_level_minimum"]
    configured = problem_mod.build_formulation(
        inputs, OptimizationConfig(budget=10_000.0, min_fulfillment=0.5),
    )
    assert any(row.name == "budget" for row in configured.rows)
    assert any(row.name == "service_level_minimum" for row in configured.rows)
    service = next(row for row in configured.rows
                   if row.name == "service_level_minimum")
    assert service.lower == pytest.approx(0.5 * configured.total_demand)


def test_parameters_declare_offers_exclusions_and_event_parameters():
    inputs = _inputs()
    formulation = problem_mod.build_formulation(inputs)
    parameters = formulation.problem.parameters
    assert parameters["eligible_offers"][0]["lead_time_days"] == 7
    assert parameters["excluded_offers"]
    assert any(item["reason"] == "product_out_of_scope"
               for item in parameters["excluded_offers"])
    assert parameters["event_point_parameters"]["event_type"] == "SUPPLIER_DISRUPTION"
    assert parameters["event_point_parameters"]["parts"][0]["supply_reduction"] == 1.0
    assert "not resampled" in parameters["event_point_parameters"]["note"]


def test_cost_objective_excludes_offers_without_unit_cost():
    case = build_case(short_outage_scenario())
    links = case["inputs"]["supplier_links"].copy()
    links.loc[links["supplier_id"] == "S1", "unit_cost"] = np.nan
    inputs = inputs_mod.build_optimization_inputs(
        case["run"], case["entities"], links,
    )
    cost_formulation = problem_mod.build_formulation(
        inputs, OptimizationConfig(objective="minimize_total_cost"),
    )
    assert not any(
        name.startswith("order[S1|") for name in cost_formulation.variable_names
    )
    assert "cost_filter_warning" in cost_formulation.problem.parameters
    shortage_formulation = problem_mod.build_formulation(
        inputs, OptimizationConfig(objective="minimize_shortage"),
    )
    assert any(
        name.startswith("order[S1|") for name in shortage_formulation.variable_names
    )


def test_empty_scope_produces_zero_column_formulation():
    case = build_case(short_outage_scenario())
    inputs = inputs_mod.build_optimization_inputs(
        case["run"], case["entities"], case["inputs"]["supplier_links"],
        product_id="NOPE",
    )
    formulation = problem_mod.build_formulation(inputs)
    assert formulation.variable_names == ()
    assert formulation.constraint_matrix.shape[1] == 0
    assert formulation.problem.decision_variables == ()
    assert formulation.problem.parameters["entity_count"] == 0


def test_source_contract_and_phase_recorded():
    formulation = problem_mod.build_formulation(_inputs())
    assert formulation.problem.source_phase == "phase_10_optimization"
    assert formulation.problem.source_contract == problem_mod.SOURCE_CONTRACT
    assert formulation.problem.source_contract == "phase_9_run_replay+v1"


def test_matrix_shapes_align_with_rows_and_columns():
    formulation = problem_mod.build_formulation(_inputs())
    row_count = len(formulation.rows)
    column_count = len(formulation.variable_names)
    assert formulation.constraint_matrix.shape == (row_count, column_count)
    assert formulation.objective_vector.shape == (column_count,)
    assert formulation.variable_lower.shape == (column_count,)
    assert formulation.variable_upper.shape == (column_count,)
    assert formulation.integrality.shape == (column_count,)
    assert formulation.total_demand == pytest.approx(
        float(sum(np.sum(entity.demand) for entity in _inputs().entities))
    )


def test_full_outage_records_exclusion_in_problem_parameters():
    formulation = problem_mod.build_formulation(_full_outage_inputs())
    excluded = formulation.problem.parameters["excluded_offers"]
    assert any(item["reason"] == "arrival_eliminated_by_scenario"
               for item in excluded)
    assert formulation.problem.parameters["eligible_offers"] == []
