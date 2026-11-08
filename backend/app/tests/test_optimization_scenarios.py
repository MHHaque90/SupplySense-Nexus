"""Phase 10 scenario-mechanics tests (spec section 25.B).

Verifies that the optimization adapter reproduces Phase 8 event
mechanics (windows, masks, arrival effects) with the scenario's
declared point parameters, and that optimization results respond to
scenario changes. All data is SYNTHETIC.
"""

from __future__ import annotations

import pytest

from backend.app.analytics.optimization import OptimizationConfig
from backend.app.analytics.optimization import inputs as inputs_mod
from backend.app.analytics.simulation import events as events_mod
from backend.app.analytics.simulation import scenarios as scenarios_mod
from backend.app.analytics.simulation import targets as targets_mod
from backend.app.analytics.simulation.types import DisruptionEvent, SimulationScenario
from backend.app.tests.optimization_support import (
    ANALYSIS_DATE,
    HORIZON_DAYS,
    build_case,
    run_case,
)
from backend.app.tests.test_optimization_inputs import _custom_scenario


def _event_scenario(event: DisruptionEvent, scenario_id: str) -> SimulationScenario:
    events_mod.validate_event(event)
    return scenarios_mod.build_scenario(
        scenario_id=scenario_id,
        event=event,
        analysis_date=ANALYSIS_DATE.isoformat(),
        horizon_days=HORIZON_DAYS,
        affected_entities=targets_mod.resolve_explicit(supplier_ids=["S1"]),
    )


def _inputs_for(scenario) -> inputs_mod.OptimizationInputs:
    case = build_case(scenario)
    return inputs_mod.build_optimization_inputs(
        case["run"], case["entities"], case["inputs"]["supplier_links"],
    )


def test_warehouse_mask_makes_hard_demand_satisfaction_infeasible():
    scenario = _custom_scenario(
        "WAREHOUSE_DISRUPTION", "S-WH-COST",
        duration_days=5, affected_suppliers=("S1",), affected_warehouses=("W1",),
        warehouse_available=False,
    )
    run = run_case(config=OptimizationConfig(objective="minimize_total_cost"),
                   case=build_case(scenario))
    assert run["result"]["status"] == "INFEASIBLE"


def test_warehouse_mask_days_force_zero_service_in_formulation():
    scenario = _custom_scenario(
        "WAREHOUSE_DISRUPTION", "S-WH-ROWS",
        duration_days=5, affected_suppliers=("S1",), affected_warehouses=("W1",),
        warehouse_available=False,
    )
    case = build_case(scenario)
    inputs = inputs_mod.build_optimization_inputs(
        case["run"], case["entities"], case["inputs"]["supplier_links"],
    )
    from backend.app.analytics.optimization import problem as problem_mod

    formulation = problem_mod.build_formulation(
        inputs, OptimizationConfig(objective="minimize_shortage"),
    )
    availability_rows = [
        row for row in formulation.rows if row.name.startswith("availability:")
    ]
    assert len(availability_rows) == 5 * len(inputs.entities)


def test_demand_shock_raises_declared_demand_and_cost():
    # A short lead keeps the shock window servable so both runs stay
    # feasible and the cost comparison is meaningful.
    from backend.app.tests.replay_support import make_inputs

    def _fast_case(scenario):
        data = make_inputs()
        links = data["supplier_links"].copy()
        links.loc[links["supplier_id"] == "S1", "lead_time_days"] = 2
        data["supplier_links"] = links
        return build_case(scenario, inputs=data)

    shock_run = run_case(config=OptimizationConfig(objective="minimize_total_cost"),
                         case=_fast_case(_custom_scenario(
                             "DEMAND_SHOCK", "S-SHOCK-COST",
                             duration_days=14, demand_multiplier=2.0,
                         )))
    base_run = run_case(config=OptimizationConfig(objective="minimize_total_cost"),
                        case=_fast_case(_custom_scenario(
                            "DEMAND_SHOCK", "S-SHOCK-BASE",
                            duration_days=14, demand_multiplier=1.0000001,
                        )))
    shock_demand = shock_run["problem"]["parameters"]["total_demand_units"]
    base_demand = base_run["problem"]["parameters"]["total_demand_units"]
    assert shock_demand > base_demand
    assert shock_run["result"]["status"] == "OPTIMAL"
    assert base_run["result"]["status"] == "OPTIMAL"
    assert shock_run["result"]["objective_value"] > base_run["result"][
        "objective_value"
    ]


def test_supply_reduction_halves_effective_order_arrival():
    scenario = _custom_scenario(
        "SUPPLY_REDUCTION", "S-RED",
        duration_days=30, supply_reduction=0.4,
    )
    inputs = _inputs_for(scenario)
    offer = next(item for item in inputs.offers if item.supplier_id == "S1")
    assert offer.arrival_day == 6
    assert offer.arrival_factor == pytest.approx(0.6)


def test_lead_time_delay_shifts_order_arrival():
    scenario = _custom_scenario(
        "LEAD_TIME_DELAY", "S-DELAY",
        duration_days=7, lead_time_delay_days=3,
    )
    inputs = _inputs_for(scenario)
    offer = next(item for item in inputs.offers if item.supplier_id == "S1")
    assert offer.arrival_day == 9
    assert offer.arrival_factor == pytest.approx(1.0)


def test_lead_time_delay_clips_late_arrival_to_final_horizon_day():
    scenario = _custom_scenario(
        "LEAD_TIME_DELAY", "S-DELAY-OUT",
        duration_days=7, lead_time_delay_days=30,
    )
    inputs = _inputs_for(scenario)
    offer = next(item for item in inputs.offers if item.supplier_id == "S1")
    assert offer.arrival_day == HORIZON_DAYS - 1
    assert offer.arrival_factor == pytest.approx(1.0)


def test_combined_event_declares_components_in_parameters():
    component = DisruptionEvent(
        event_id="E-C1",
        event_type="SUPPLIER_DISRUPTION",
        name="component",
        duration_days=3,
        affected_suppliers=["S1"],
        supply_reduction=1.0,
    )
    combined = DisruptionEvent(
        event_id="E-COMB",
        event_type="COMBINED_DISRUPTION",
        name="combined",
        duration_days=14,
        components=[component],
    )
    case = build_case(_event_scenario(combined, "S-COMB"))
    inputs = inputs_mod.build_optimization_inputs(
        case["run"], case["entities"], case["inputs"]["supplier_links"],
    )
    assert inputs.event is not None
    assert inputs.event["event_type"] == "COMBINED_DISRUPTION"
    assert len(inputs.event["components"]) == 1
    from backend.app.analytics.optimization import problem as problem_mod

    formulation = problem_mod.build_formulation(inputs)
    parameters = formulation.problem.parameters["event_point_parameters"]
    assert parameters["event_type"] == "COMBINED_DISRUPTION"
    assert parameters["parts"] == [{
        "event_type": "SUPPLIER_DISRUPTION",
        "supply_reduction": 1.0,
        "lead_time_delay_days": 0,
        "demand_multiplier": 1.0,
    }]


def test_scenario_probability_and_seed_do_not_change_the_problem_id():
    first = run_case(
        case=build_case(_custom_scenario(
            "DEMAND_SHOCK", "S-SEED",
            duration_days=5, demand_multiplier=1.2,
        )),
    )
    event = DisruptionEvent(
        event_id="E-SEED2",
        event_type="DEMAND_SHOCK",
        name="shock",
        duration_days=5,
        demand_multiplier=1.2,
    )
    other_scenario = scenarios_mod.build_scenario(
        scenario_id="S-SEED",
        event=event,
        analysis_date=ANALYSIS_DATE.isoformat(),
        horizon_days=HORIZON_DAYS,
        simulation_count=17,
        random_seed=99,
        affected_entities=targets_mod.resolve_explicit(supplier_ids=["S1"]),
    )
    second = run_case(case=build_case(other_scenario))
    assert first["problem"]["problem_id"] == second["problem"]["problem_id"]
    assert first["result"]["objective_value"] == second["result"]["objective_value"]


def test_event_point_parameters_recorded_in_run():
    run = run_case(case=build_case(_custom_scenario(
        "DEMAND_SHOCK", "S-POINT",
        duration_days=5, demand_multiplier=1.2,
    )))
    parameters = run["problem"]["parameters"]["event_point_parameters"]
    assert parameters["event_type"] == "DEMAND_SHOCK"
    assert parameters["parts"][0]["demand_multiplier"] == 1.2
    assert "not resampled" in parameters["note"]


def test_scenario_change_alters_problem_id():
    short = run_case(case=build_case(_custom_scenario(
        "DEMAND_SHOCK", "S-A", duration_days=5, demand_multiplier=1.2,
    )))
    long = run_case(case=build_case(_custom_scenario(
        "DEMAND_SHOCK", "S-B", duration_days=14, demand_multiplier=1.2,
    )))
    assert short["problem"]["problem_id"] != long["problem"]["problem_id"]
