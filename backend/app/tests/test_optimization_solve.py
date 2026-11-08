"""Phase 10 solver and feasibility tests (spec section 25.D).

Covers the four declared objectives, the six allowed solver statuses,
infeasibility diagnostics, budget/service-level enforcement, NO_DATA,
integer vs continuous modes, and validation outcomes. SYNTHETIC data.
"""

from __future__ import annotations

import pytest

from backend.app.analytics.optimization import (
    OBJECTIVES,
    STATUSES,
    OptimizationConfig,
    run_optimization,
)
from backend.app.tests.optimization_support import (
    build_case,
    run_case,
    short_outage_scenario,
)

FULL_OUTAGE = "minimize_total_cost"


def test_status_always_in_declared_set():
    run = run_case(config=OptimizationConfig(objective=FULL_OUTAGE),
                   case=build_case())
    assert run["result"]["status"] in STATUSES
    assert run["result"]["feasible"] is False
    assert run["result"]["objective_value"] is None


def test_cost_objective_infeasible_when_arrival_eliminated():
    run = run_case(config=OptimizationConfig(objective=FULL_OUTAGE),
                   case=build_case())
    result = run["result"]
    assert result["status"] == "INFEASIBLE"
    assert result["decision_values"] == {}
    assert run["diagnostics"]
    assert any("No eligible supplier offers" in item for item in run["diagnostics"])
    assert any("lead-time horizon rule" in item for item in run["diagnostics"])
    assert result["baseline_comparison"]["status"] == "unavailable"


def test_cost_objective_optimal_when_short_outage_keeps_offer_eligible():
    run = run_case(config=OptimizationConfig(objective=FULL_OUTAGE),
                   case=build_case(short_outage_scenario()))
    result = run["result"]
    assert result["status"] == "OPTIMAL"
    assert result["feasible"] is True
    decisions = result["decision_values"]
    assert decisions
    assert all(value > 0 for value in decisions.values())
    assert all(abs(value - round(value)) < 1e-9 for value in decisions.values())
    breakdown = result["objective_breakdown"]
    assert breakdown["total_unmet_demand"] == pytest.approx(0.0)
    assert breakdown["total_served_demand"] == pytest.approx(560.0)
    assert breakdown["fulfillment_rate"] == pytest.approx(1.0)
    assert breakdown["total_procurement_cost"] == pytest.approx(4500.0)
    assert result["objective_value"] == pytest.approx(4500.0)
    checks = {item["name"]: item["status"] for item in run["checks"]}
    assert checks == {
        "scope_consistency": "PASS",
        "provenance_completeness": "PASS",
        "objective_arithmetic": "PASS",
        "decision_bounds": "PASS",
        "decision_integrality": "PASS",
        "row_feasibility": "PASS",
        "inventory_cross_check": "PASS",
    }
    binding = result["binding_constraints"]
    assert any(name.startswith("demand_satisfaction:P1|") for name in binding)
    assert not any(name.startswith("daily_") for name in binding)


def test_missing_capacity_surfaces_unchecked_warning():
    run = run_case(config=OptimizationConfig(objective=FULL_OUTAGE),
                   case=build_case(short_outage_scenario()))
    warnings = " ".join(run["result"]["warnings"])
    assert "UNCHECKED: capacity_units missing" in warnings


def test_minimize_shortage_prices_no_cost_and_reports_unmet():
    run = run_case(config=OptimizationConfig(objective="minimize_shortage"),
                   case=build_case())
    result = run["result"]
    assert result["status"] == "OPTIMAL"
    assert result["objective_value"] == pytest.approx(480.0)
    assert result["objective_breakdown"]["total_unmet_demand"] == pytest.approx(480.0)
    assert result["objective_breakdown"]["total_procurement_cost"] == pytest.approx(0.0)


def test_minimize_shortage_orders_when_supply_can_close_the_gap():
    case = build_case(short_outage_scenario())
    full = run_case(config=OptimizationConfig(objective="minimize_shortage"), case=case)
    assert full["result"]["status"] == "OPTIMAL"
    assert full["result"]["objective_value"] == pytest.approx(0.0)
    assert full["result"]["decision_values"]


def test_tradeoff_requires_explicit_positive_penalty():
    case = build_case()
    with pytest.raises(ValueError, match="shortage_penalty_per_unit"):
        run_optimization(
            case["run"], case["entities"], case["inputs"]["supplier_links"],
            config=OptimizationConfig(objective="cost_shortage_tradeoff"),
        )
    with pytest.raises(ValueError, match="positive"):
        run_optimization(
            case["run"], case["entities"], case["inputs"]["supplier_links"],
            config=OptimizationConfig(
                objective="cost_shortage_tradeoff", shortage_penalty_per_unit=0.0,
            ),
        )


def test_tradeoff_objective_recomputes_from_components():
    run = run_case(
        config=OptimizationConfig(
            objective="cost_shortage_tradeoff", shortage_penalty_per_unit=25.0,
        ),
        case=build_case(),
    )
    breakdown = run["result"]["objective_breakdown"]
    expected = (
        breakdown["total_procurement_cost"] + 25.0 * breakdown["total_unmet_demand"]
    )
    assert run["result"]["objective_value"] == pytest.approx(expected)
    assert breakdown["shortage_penalty_cost"] == pytest.approx(12000.0)


def test_maximize_fulfillment_reports_served_units():
    run = run_case(
        config=OptimizationConfig(objective="maximize_service_fulfillment"),
        case=build_case(),
    )
    result = run["result"]
    assert result["status"] == "OPTIMAL"
    assert result["objective_value"] == pytest.approx(80.0)
    assert result["objective_breakdown"]["total_served_demand"] == pytest.approx(80.0)
    assert run["problem"]["objective"]["direction"] == "maximize"


def test_all_four_objectives_stay_in_declared_tuple():
    assert len(OBJECTIVES) == 4
    for key in OBJECTIVES:
        assert key in (
            "minimize_total_cost", "minimize_shortage",
            "cost_shortage_tradeoff", "maximize_service_fulfillment",
        )


def test_impossible_budget_is_infeasible_with_diagnostic():
    run = run_case(
        config=OptimizationConfig(objective=FULL_OUTAGE, budget=1.0),
        case=build_case(short_outage_scenario()),
    )
    assert run["result"]["status"] == "INFEASIBLE"
    assert any("exceeds the configured budget" in item for item in run["diagnostics"])


def test_configured_budget_is_respected_when_feasible():
    run = run_case(
        config=OptimizationConfig(objective=FULL_OUTAGE, budget=10_000.0),
        case=build_case(short_outage_scenario()),
    )
    assert run["result"]["status"] == "OPTIMAL"
    assert run["result"]["objective_breakdown"]["total_procurement_cost"] <= 10_000.0
    assert any(row["name"] == "budget"
               for row in run["problem"]["constraints"])


def test_service_level_floor_infeasible_when_disruption_blocks_service():
    run = run_case(
        config=OptimizationConfig(objective="minimize_shortage",
                                  min_fulfillment=1.0),
        case=build_case(),
    )
    assert run["result"]["status"] == "INFEASIBLE"
    assert run["diagnostics"]


def test_service_level_floor_feasible_when_orders_can_reach_it():
    run = run_case(
        config=OptimizationConfig(objective="minimize_shortage",
                                  min_fulfillment=1.0),
        case=build_case(short_outage_scenario()),
    )
    assert run["result"]["status"] == "OPTIMAL"
    assert run["result"]["objective_breakdown"]["fulfillment_rate"] == pytest.approx(1.0)


def test_no_data_for_empty_scope_without_solver_call():
    run = run_case(case=build_case(short_outage_scenario()), product_id="NOPE")
    result = run["result"]
    assert result["status"] == "NO_DATA"
    assert result["feasible"] is False
    assert result["decision_values"] == {}
    joined = " ".join(result["warnings"])
    assert "No decision variables in scope" in joined
    assert "NO_DATA" in joined
    checks = {item["name"]: item["status"] for item in run["checks"]}
    assert checks["row_feasibility"] == "UNCHECKED"
    assert checks["inventory_cross_check"] == "UNCHECKED"
    assert checks["scope_consistency"] == "PASS"


def test_continuous_mode_is_valid_and_marks_integrality_unchecked():
    run = run_case(
        config=OptimizationConfig(objective=FULL_OUTAGE,
                                  quantity_integrality="continuous"),
        case=build_case(short_outage_scenario()),
    )
    assert run["result"]["status"] == "OPTIMAL"
    checks = {item["name"]: item["status"] for item in run["checks"]}
    assert checks["decision_integrality"] == "UNCHECKED"
    assert checks["decision_bounds"] == "PASS"


def test_solver_and_version_are_declared():
    run = run_case(config=OptimizationConfig(objective=FULL_OUTAGE),
                   case=build_case(short_outage_scenario()))
    assert run["result"]["solver"] == "scipy-milp-highs"
    assert "scipy" in run["result"]["solver_version"]


def test_run_payload_carries_timings_and_labels():
    run = run_case(config=OptimizationConfig(objective=FULL_OUTAGE),
                   case=build_case(short_outage_scenario()))
    assert run["synthetic"] is True
    assert run["data_source_label"] == "simulated"
    for key in ("input_preparation", "problem_construction", "solver",
                "result_validation", "total"):
        assert run["timings"][key] >= 0.0
    assert run["timings"]["total"] < 5.0
