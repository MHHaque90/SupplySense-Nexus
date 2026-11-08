"""Phase 9 end-to-end integration tests (all eight decision types)."""

import json
import time

from backend.app.analytics.replay import decisions, reports
from backend.app.analytics.replay.types import DECISION_TYPES
from backend.app.tests.replay_support import (
    make_inputs,
    make_scenario,
    run_replay_for,
)

EXPECTED_CHAIN = [
    "scenario", "event", "decision", "supplier/product/warehouse",
    "baseline", "decision_effect", "simulation", "outcome",
]


def _all_eight_arms(replay_id: str = "replay-S-REPLAY"):
    return [
        decisions.build_no_action(replay_id),
        decisions.build_decision(
            replay_id, "EXPEDITE_INBOUND",
            affected_suppliers=["S1"], affected_products=["P1"],
            affected_warehouses=["W1"],
            quantities={"expedite_units": 30.0},
            timing={"start_day": 0, "end_day": 14, "delay_reduction_days": 3},
        ),
        decisions.build_decision(
            replay_id, "ALTERNATIVE_SUPPLIER",
            affected_suppliers=["S1"], affected_products=["P1"],
            affected_warehouses=["W1"],
            quantities={"rerouted_units": 20.0},
        ),
        decisions.build_decision(
            replay_id, "SUPPLIER_ALLOCATION_CHANGE",
            affected_suppliers=["S1"], affected_products=["P1"],
            quantities={"S1": 100.0},
        ),
        decisions.build_decision(
            replay_id, "INVENTORY_TRANSFER",
            affected_products=["P1"], affected_warehouses=["W1", "W2"],
            quantities={"transfer_units": 15.0},
        ),
        decisions.build_decision(
            replay_id, "DEMAND_ADJUSTMENT",
            affected_products=["P1"], affected_warehouses=["W1"],
            quantities={"demand_multiplier": 0.9},
            timing={"start_day": 0, "end_day": 14},
        ),
        decisions.build_decision(
            replay_id, "PURCHASE_ORDER_ADJUSTMENT",
            affected_suppliers=["S1"], affected_products=["P1"],
            quantities={"order_units": 75.0},
            timing={"arrival_day": 3},
        ),
        decisions.build_decision(
            replay_id, "COMBINED_ACTION",
            components=[
                decisions.build_decision(
                    replay_id, "DEMAND_ADJUSTMENT",
                    affected_products=["P1"], affected_warehouses=["W1"],
                    quantities={"demand_multiplier": 1.1},
                    timing={"start_day": 0, "end_day": 14},
                ),
                decisions.build_decision(
                    replay_id, "PURCHASE_ORDER_ADJUSTMENT",
                    affected_suppliers=["S1"], affected_products=["P1"],
                    quantities={"order_units": 40.0},
                    timing={"arrival_day": 5},
                ),
            ],
        ),
    ]


def _run_all_eight():
    return run_replay_for(
        _all_eight_arms(), make_scenario(), make_inputs())


def test_every_decision_type_replays_with_full_report_pipeline():
    started = time.perf_counter()
    run = _run_all_eight()
    report = reports.build_report(run)
    markdown = reports.render_markdown(report)
    elapsed = time.perf_counter() - started

    assert {result.decision_type for result in run["results"]} == set(DECISION_TYPES)
    assert len(run["results"]) == 8
    assert len(run["pairwise"]) == 28
    assert report["replay_metadata"]["decision_count"] == 8
    assert set(report) == set(reports.REPORT_SECTIONS)
    assert len([
        line for line in markdown.splitlines() if line.startswith("## ")
    ]) == 21
    json.dumps(report, default=str)
    for result in run["results"]:
        assert result.decision_id in markdown
    assert elapsed < 30.0, f"8-arm replay took {elapsed:.1f}s"


def test_every_arm_shares_one_sample_fingerprint():
    run = _run_all_eight()
    fingerprints = {result.sample_fingerprint for result in run["results"]}
    assert fingerprints == {run["sample_fingerprint"]}


def test_validation_constraints_and_effects_recorded_for_every_arm():
    run = _run_all_eight()
    for result in run["results"]:
        assert any(note.startswith("PASS") for note in result.validation)
        assert result.constraint_notes
        assert result.effect_notes
        assert result.traceability["entities"]


def test_traceability_chains_are_complete_and_decision_scoped():
    run = _run_all_eight()
    for result in run["results"]:
        traces = result.traceability["entities"]
        assert traces
        for trace in traces:
            assert trace["chain"] == EXPECTED_CHAIN
            assert trace["decision_id"] == result.decision_id
            assert trace["decision_type"] == result.decision_type
            assert trace["baseline_ref"] == run["baseline_ref"]
            assert trace["decision_assumptions"]


def test_baseline_is_identical_objective_value_for_all_reports():
    run = _run_all_eight()
    baseline = run["baseline"].to_dict()
    report = reports.build_report(run)
    assert report["shared_baseline"]["outcome"] == baseline
    for deltas in run["baseline_deltas"].values():
        assert set(deltas) == {
            "delta_stockout_probability", "delta_unmet_demand",
            "delta_min_inventory", "delta_ending_inventory",
            "delta_stockout_days", "delta_service_exposure",
        }
