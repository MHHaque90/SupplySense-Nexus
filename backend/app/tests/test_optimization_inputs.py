"""Phase 10 input-adapter tests (spec section 25.A).

The adapter consumes only public Phase 9 outputs and mirrors Phase 8
``run_entity_once`` dispatch with declared point parameters. All data
here is SYNTHETIC and built in memory.
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.analytics.optimization import inputs as inputs_mod
from backend.app.analytics.optimization.inputs import build_optimization_inputs
from backend.app.analytics.simulation import events as events_mod
from backend.app.analytics.simulation import inventory_engine
from backend.app.analytics.simulation import scenarios as scenarios_mod
from backend.app.analytics.simulation import targets as targets_mod
from backend.app.analytics.simulation.types import DisruptionEvent, SimulationScenario
from backend.app.tests.optimization_support import (
    ANALYSIS_DATE,
    HORIZON_DAYS,
    build_case,
    make_scenario,
    short_outage_scenario,
)


def _custom_scenario(
    event_type: str,
    scenario_id: str,
    *,
    duration_days: int = 7,
    affected_suppliers: tuple[str, ...] = ("S1",),
    affected_warehouses: tuple[str, ...] = (),
    demand_multiplier: float = 1.0,
    supply_reduction: float = 0.0,
    warehouse_available: bool = True,
    lead_time_delay_days: int = 0,
) -> SimulationScenario:
    """Build one validated scenario with an explicit event type."""
    event = DisruptionEvent(
        event_id=f"E-{event_type}",
        event_type=event_type,
        name=event_type,
        description="",
        start_date="",
        duration_days=duration_days,
        affected_suppliers=list(affected_suppliers),
        affected_products=[],
        affected_warehouses=list(affected_warehouses),
        supply_reduction=supply_reduction,
        lead_time_delay_days=lead_time_delay_days,
        demand_multiplier=demand_multiplier,
        warehouse_available=warehouse_available,
        assumptions=[],
    )
    events_mod.validate_event(event)
    supplier_ids = list(affected_suppliers)
    warehouse_ids = list(affected_warehouses)
    return scenarios_mod.build_scenario(
        scenario_id=scenario_id,
        event=event,
        analysis_date=ANALYSIS_DATE.isoformat(),
        horizon_days=HORIZON_DAYS,
        affected_entities=targets_mod.resolve_explicit(
            supplier_ids=supplier_ids, warehouse_ids=warehouse_ids,
        ),
    )


def _inputs_for(case, **kwargs) -> inputs_mod.OptimizationInputs:
    return build_optimization_inputs(
        case["run"], case["entities"], case["inputs"]["supplier_links"], **kwargs,
    )


def test_malformed_replay_run_names_missing_keys():
    case = build_case()
    broken = {key: value for key, value in case["run"].items() if key != "uncertainty"}
    with pytest.raises(ValueError, match="uncertainty"):
        build_optimization_inputs(broken, case["entities"], case["inputs"]["supplier_links"])


def test_malformed_scenario_names_missing_keys():
    case = build_case()
    broken = dict(case["run"])
    scenario = dict(case["run"]["scenario"])
    scenario.pop("horizon_days")
    broken["scenario"] = scenario
    with pytest.raises(ValueError, match="horizon_days"):
        build_optimization_inputs(
            broken, case["entities"], case["inputs"]["supplier_links"],
        )


def test_nonpositive_scenario_horizon_rejected():
    case = build_case()
    broken = dict(case["run"])
    scenario = dict(case["run"]["scenario"])
    scenario["horizon_days"] = 0
    broken["scenario"] = scenario
    with pytest.raises(ValueError, match="positive"):
        build_optimization_inputs(
            broken, case["entities"], case["inputs"]["supplier_links"],
        )


def test_missing_supplier_link_column_is_named():
    case = build_case()
    links = case["inputs"]["supplier_links"].drop(columns=["unit_cost"])
    with pytest.raises(ValueError, match="unit_cost"):
        build_optimization_inputs(case["run"], case["entities"], links)


def test_malformed_entity_names_missing_keys():
    case = build_case()
    broken_entity = dict(case["entities"][0])
    broken_entity.pop("schedule")
    with pytest.raises(ValueError, match="schedule"):
        build_optimization_inputs(
            case["run"], [broken_entity], case["inputs"]["supplier_links"],
        )


def test_new_order_arrives_at_lead_time_minus_one():
    case = build_case(short_outage_scenario())
    inputs = _inputs_for(case)
    offer = next(item for item in inputs.offers if item.supplier_id == "S1")
    assert offer.lead_time_days == 7
    assert offer.arrival_day == 6
    assert offer.arrival_factor == pytest.approx(1.0)


def test_full_outage_excludes_order_arrival_with_reason():
    case = build_case(make_scenario())
    inputs = _inputs_for(case)
    assert inputs.offers == ()
    reasons = {(item["supplier_id"], item["product_id"]): item["reason"]
               for item in inputs.excluded_offers}
    assert reasons[("S1", "P1")] == "arrival_eliminated_by_scenario"


def test_lead_time_outside_horizon_excluded():
    case = build_case(short_outage_scenario())
    links = case["inputs"]["supplier_links"].copy()
    links.loc[links["supplier_id"] == "S1", "lead_time_days"] = 40
    inputs = build_optimization_inputs(
        case["run"], case["entities"], links,
    )
    reasons = {item["reason"] for item in inputs.excluded_offers}
    assert "lead_time_outside_horizon" in reasons


def test_nonpositive_lead_time_excluded():
    case = build_case(short_outage_scenario())
    links = case["inputs"]["supplier_links"].copy()
    links.loc[links["supplier_id"] == "S1", "lead_time_days"] = 0
    inputs = build_optimization_inputs(case["run"], case["entities"], links)
    reasons = {item["reason"] for item in inputs.excluded_offers}
    assert "lead_time_nonpositive" in reasons


def test_scope_filters_drop_entities_and_offers():
    case = build_case(short_outage_scenario())
    inputs = _inputs_for(case, product_id="P2")
    assert inputs.entities == ()
    assert inputs.offers == ()


def test_missing_capacity_and_unit_cost_produce_unchecked_warnings():
    case = build_case(short_outage_scenario())
    links = case["inputs"]["supplier_links"].copy()
    links.loc[links["supplier_id"] == "S1", "unit_cost"] = np.nan
    inputs = build_optimization_inputs(case["run"], case["entities"], links)
    joined = " ".join(inputs.warnings)
    assert "capacity_units missing" in joined
    assert "unit_cost missing" in joined
    assert all("UNCHECKED:" in item for item in inputs.warnings)


def test_warehouse_disruption_masks_declared_days():
    scenario = _custom_scenario(
        "WAREHOUSE_DISRUPTION", "S-WH",
        duration_days=5, affected_suppliers=("S1",), affected_warehouses=("W1",),
        warehouse_available=False,
    )
    case = build_case(scenario)
    inputs = _inputs_for(case)
    assert {entity.warehouse_id for entity in inputs.entities} == {"W1", "W2"}
    # run_entity_once masks every entity for the window; the Phase 10
    # adapter mirrors that dispatch exactly.
    for entity in inputs.entities:
        assert entity.available[:5] == (False,) * 5
        assert entity.available[5:] == (True,) * (HORIZON_DAYS - 5)


def test_demand_shock_multiplies_declared_window():
    scenario = _custom_scenario(
        "DEMAND_SHOCK", "S-SHOCK",
        duration_days=7, demand_multiplier=2.0,
    )
    case = build_case(scenario)
    inputs = _inputs_for(case)
    for entity in inputs.entities:
        assert entity.demand[:7] == (20.0,) * 7
        assert entity.demand[7:] == (10.0,) * (HORIZON_DAYS - 7)
        assert entity.demand_lower[0] == pytest.approx(16.0)
        assert entity.demand_upper[0] == pytest.approx(24.0)


def test_existing_inbound_passes_through_supply_effects():
    case = build_case(make_scenario())
    inputs = _inputs_for(case)
    for entity in inputs.entities:
        assert sum(entity.existing_inbound) == 0.0


def test_point_parameters_and_assumptions_documented():
    case = build_case()
    inputs = _inputs_for(case)
    joined = " ".join(inputs.assumptions)
    assert "point parameters" in joined
    assert "not resampled" in joined
    assert inputs.uncertainty["requirement_intervals"]["bounds_source"] == (
        "phase4_intervals_adjusted_by_scenario_point_parameters"
    )


def test_baseline_unmet_matches_phase8_daily_engine():
    case = build_case(make_scenario())
    inputs = _inputs_for(case)
    for entity in inputs.entities:
        run = inventory_engine.run_days(
            entity.on_hand,
            np.asarray(entity.demand, dtype=float),
            np.asarray(entity.existing_inbound, dtype=float),
            np.asarray(entity.available, dtype=bool),
        )
        assert entity.baseline_unmet == pytest.approx(float(np.sum(run["unmet"])))
        assert entity.baseline_served == pytest.approx(
            float(np.sum(entity.demand)) - float(np.sum(run["unmet"]))
        )


def test_provenance_and_forecast_references_present():
    case = build_case()
    inputs = _inputs_for(case)
    provenance = inputs.provenance
    assert provenance.source_phase == "phase_9_decision_replay"
    assert provenance.replay_id.startswith("replay-")
    assert provenance.scenario_fingerprint
    assert provenance.baseline_ref
    assert provenance.sample_fingerprint
    assert provenance.analysis_date == ANALYSIS_DATE.isoformat()
    assert provenance.synthetic is True
    assert provenance.data_source_label == "simulated"
    assert inputs.forecast_references
    assert all(
        reference["model_name"] == "synthetic-forecast"
        for reference in inputs.forecast_references
    )


def test_no_action_outcome_and_scenario_impact_recorded():
    case = build_case()
    inputs = _inputs_for(case)
    assert inputs.no_action_outcome is not None
    assert inputs.scenario_impact is not None
    assert inputs.scenario_impact["basis"] == (
        "phase9_no_action_arm_minus_phase9_baseline"
    )
    assert inputs.baseline_outcome["expected_unmet_demand"] is not None
