"""Phase 9 comparison tests (baseline deltas, pairwise deltas, no ranking)."""

from backend.app.analytics.replay import comparison, decisions
from backend.app.analytics.simulation.types import ScenarioOutcome
from backend.app.tests.replay_support import run_replay_for

DELTA_KEYS = {
    "delta_stockout_probability", "delta_unmet_demand", "delta_min_inventory",
    "delta_ending_inventory", "delta_stockout_days", "delta_service_exposure",
}


def _outcome(label: str, unmet: float, stockout_probability: float) -> ScenarioOutcome:
    outcome = ScenarioOutcome(label=label)
    outcome.expected_unmet_demand = unmet
    outcome.stockout_probability = stockout_probability
    outcome.expected_min_inventory = 10.0
    outcome.expected_ending_inventory = 5.0
    outcome.expected_stockout_days = 2.0
    outcome.service_exposure_probability = 0.5
    return outcome


def _arms():
    return [
        decisions.build_no_action("replay-S-REPLAY"),
        decisions.build_decision(
            "replay-S-REPLAY", "PURCHASE_ORDER_ADJUSTMENT",
            affected_suppliers=["S1"], affected_products=["P1"],
            affected_warehouses=["W1"],
            quantities={"order_units": 25.0},
            timing={"arrival_day": 3},
        ),
        decisions.build_decision(
            "replay-S-REPLAY", "DEMAND_ADJUSTMENT",
            affected_products=["P1"], affected_warehouses=["W1"],
            quantities={"demand_multiplier": 0.9},
            timing={"start_day": 0, "end_day": 14},
        ),
    ]


def test_baseline_comparison_reports_every_delta_key():
    run = run_replay_for(_arms())
    assert len(run["baseline_deltas"]) == 3
    for deltas in run["baseline_deltas"].values():
        assert set(deltas) == DELTA_KEYS


def test_pairwise_comparison_covers_every_pair_in_declared_order():
    run = run_replay_for(_arms())
    ids = [result.decision_id for result in run["results"]]
    expected = [(ids[i], ids[j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]
    actual = [(item["left_decision_id"], item["right_decision_id"])
              for item in run["pairwise"]]
    assert actual == expected
    assert len(run["pairwise"]) == 3


def test_pairwise_deltas_are_right_minus_left():
    left = _outcome("decision", unmet=100.0, stockout_probability=0.8)
    right = _outcome("decision", unmet=80.0, stockout_probability=0.6)
    pairs = comparison.pairwise([("NO_ACTION", "A", left), ("EXPEDITE_INBOUND", "B", right)])
    assert len(pairs) == 1
    assert pairs[0]["deltas"]["delta_unmet_demand"] == -20.0
    assert abs(pairs[0]["deltas"]["delta_stockout_probability"] + 0.2) < 1e-9
    assert pairs[0]["left_decision_id"] == "A"
    assert pairs[0]["right_decision_id"] == "B"


def test_pairwise_swapping_order_flips_sign():
    left = _outcome("decision", unmet=100.0, stockout_probability=0.8)
    right = _outcome("decision", unmet=80.0, stockout_probability=0.6)
    forward = comparison.pairwise([("T", "A", left), ("T", "B", right)])[0]["deltas"]
    backward = comparison.pairwise([("T", "B", right), ("T", "A", left)])[0]["deltas"]
    assert forward["delta_unmet_demand"] == -backward["delta_unmet_demand"]
    assert forward["delta_min_inventory"] == -backward["delta_min_inventory"]


def test_identical_arms_produce_zero_deltas():
    outcome = _outcome("decision", unmet=42.0, stockout_probability=0.5)
    pairs = comparison.pairwise([("T", "A", outcome), ("T", "B", outcome)])
    assert all(value == 0.0 for value in pairs[0]["deltas"].values())


def test_none_values_propagate_as_none():
    baseline = ScenarioOutcome(label="baseline")
    arm = ScenarioOutcome(label="decision")
    baseline.p90_unmet_demand = None
    arm.p90_unmet_demand = None
    deltas = comparison.compare_to_baseline(baseline, [("T", "A", arm)])
    assert deltas["A"]["delta_stockout_probability"] is None
    assert deltas["A"]["delta_unmet_demand"] is None
    assert set(deltas["A"]) == DELTA_KEYS


def test_pairwise_contains_no_ranking_fields():
    run = run_replay_for(_arms())
    for pair in run["pairwise"]:
        assert set(pair) == {
            "left_decision_id", "left_decision_type", "right_decision_id",
            "right_decision_type", "deltas", "semantics",
        }
        for key in pair["deltas"]:
            assert key.startswith("delta_")


def test_result_deltas_helper_returns_recorded_baseline_deltas():
    run = run_replay_for(_arms())
    recorded = comparison.result_deltas(run["results"])
    assert set(recorded) == set(run["baseline_deltas"])
    for decision_id, deltas in recorded.items():
        assert deltas == run["baseline_deltas"][decision_id]
