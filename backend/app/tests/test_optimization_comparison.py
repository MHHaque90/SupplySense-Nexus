"""Phase 10 baseline/scenario comparison tests (spec section 25.E).

Baseline comparison uses identical deterministic accounting on both
sides; scenario comparison carries Phase 9 factual deltas and never
re-simulates the optimized plan. All data is SYNTHETIC.
"""

from __future__ import annotations

import pytest

from backend.app.analytics.optimization import OptimizationConfig
from backend.app.analytics.optimization import comparison as comparison_mod
from backend.app.analytics.optimization import inputs as inputs_mod
from backend.app.tests.optimization_support import (
    build_case,
    run_case,
    short_outage_scenario,
)


def _inputs_for(case) -> inputs_mod.OptimizationInputs:
    return inputs_mod.build_optimization_inputs(
        case["run"], case["entities"], case["inputs"]["supplier_links"],
    )


def test_baseline_comparison_uses_deterministic_point_accounting():
    run = run_case(config=OptimizationConfig(objective="minimize_total_cost"),
                   case=build_case(short_outage_scenario()))
    comparison = run["result"]["baseline_comparison"]
    assert comparison["basis"] == "phase_10_deterministic_point_accounting"
    current = comparison["current_plan"]
    combined = comparison["current_plan_plus_optimized_orders"]
    assert current["unmet_demand_units"] == pytest.approx(360.0)
    assert combined["unmet_demand_units"] == pytest.approx(0.0)
    assert combined["fulfillment_rate"] == pytest.approx(1.0)
    assert combined["procurement_cost"] == pytest.approx(4500.0)
    assert "not the Phase 9 Monte Carlo baseline" in current["note"]
    assert "identical deterministic accounting" in comparison["note"]


def test_baseline_comparison_deltas_are_arithmetically_consistent():
    run = run_case(config=OptimizationConfig(objective="minimize_total_cost"),
                   case=build_case(short_outage_scenario()))
    comparison = run["result"]["baseline_comparison"]
    current = comparison["current_plan"]
    combined = comparison["current_plan_plus_optimized_orders"]
    deltas = comparison["deltas"]
    assert deltas["unmet_delta"] == pytest.approx(
        combined["unmet_demand_units"] - current["unmet_demand_units"]
    )
    assert deltas["served_delta"] == pytest.approx(
        combined["served_demand_units"] - current["served_demand_units"]
    )
    assert deltas["added_procurement_cost"] == pytest.approx(4500.0)
    assert deltas["fulfillment_rate_delta"] == pytest.approx(
        combined["fulfillment_rate"] - current["fulfillment_rate"]
    )
    assert deltas["unmet_delta"] < 0


def test_infeasible_run_marks_baseline_comparison_unavailable():
    run = run_case(config=OptimizationConfig(objective="minimize_total_cost"),
                   case=build_case())
    comparison = run["result"]["baseline_comparison"]
    assert comparison["status"] == "unavailable"
    assert "No feasible solution vector" in comparison["note"]


def test_evaluate_plan_by_entity_covers_every_entity():
    case = build_case(short_outage_scenario())
    inputs = _inputs_for(case)
    plan = comparison_mod.evaluate_plan(inputs, {"order[S1|P1|W1]": 180.0})
    assert len(plan["by_entity"]) == len(inputs.entities)
    assert plan["procurement_cost"] == pytest.approx(180.0 * 12.5)


def test_scenario_comparison_carries_phase9_deltas():
    run = run_case(case=build_case(short_outage_scenario()))
    comparison = run["result"]["scenario_comparison"]
    assert comparison["basis"] == "phase9_no_action_arm_minus_phase9_baseline"
    assert comparison["accounting"] == "phase9_monte_carlo"
    assert "deltas" in comparison
    assert comparison["optimization_not_resimulated"] is True
    assert "not re-simulated" in comparison["limitation"]
    assert "expected_unmet_demand" in comparison["phase9_baseline_outcome"]
    assert "stockout_probability" in comparison["phase9_no_action_outcome"]


def test_scenario_comparison_unavailable_without_no_action_arm():
    case = build_case(short_outage_scenario())
    stripped = dict(case["run"])
    stripped["results"] = []
    inputs = inputs_mod.build_optimization_inputs(
        stripped, case["entities"], case["inputs"]["supplier_links"],
    )
    comparison = comparison_mod.build_scenario_comparison(inputs)
    assert comparison["basis"] == "unavailable"
    assert comparison["optimization_not_resimulated"] is True


def test_comparison_outputs_are_json_serializable():
    import json

    run = run_case(config=OptimizationConfig(objective="minimize_total_cost"),
                   case=build_case(short_outage_scenario()))
    payload = {
        "baseline": run["result"]["baseline_comparison"],
        "scenario": run["result"]["scenario_comparison"],
    }
    assert json.loads(json.dumps(payload, default=str)) == payload
