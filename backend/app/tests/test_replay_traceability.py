"""Phase 9 traceability tests (decision fields added to the Phase 8 chain)."""

from backend.app.analytics.replay import decisions, traceability
from backend.app.tests.replay_support import run_replay_for

DECISION_FIELDS = {
    "decision_id", "decision_type", "decision_assumptions", "baseline_ref",
}
CHAIN = [
    "scenario", "event", "decision", "supplier/product/warehouse",
    "baseline", "decision_effect", "simulation", "outcome",
]


def _arms(replay_id: str = "replay-S-REPLAY"):
    return [
        decisions.build_no_action(replay_id),
        decisions.build_decision(
            replay_id, "EXPEDITE_INBOUND",
            affected_suppliers=["S1"], affected_products=["P1"],
            affected_warehouses=["W1"],
            quantities={"expedite_units": 30.0},
            timing={"start_day": 0, "end_day": 14, "delay_reduction_days": 3},
            assumptions=["Expedited inbound arrives earlier."],
        ),
    ]


def test_every_trace_carries_decision_fields():
    run = run_replay_for(_arms())
    for result in run["results"]:
        traces = result.traceability["entities"]
        assert traces
        for trace in traces:
            assert DECISION_FIELDS <= set(trace)
            assert trace["decision_id"] == result.decision_id
            assert trace["decision_type"] == result.decision_type
            assert trace["baseline_ref"] == run["baseline_ref"]
            assert isinstance(trace["decision_assumptions"], list)
            assert trace["decision_assumptions"]


def test_trace_keeps_phase8_provenance_fields():
    run = run_replay_for(_arms())
    trace = run["results"][0].traceability["entities"][0]
    for field in (
        "scenario_id", "event_id", "event_type", "product_id", "warehouse_id",
        "supplier_ids", "baseline_on_hand", "forecast_model", "random_seed",
        "simulation_count", "data_source_label",
    ):
        assert field in trace
    assert trace["scenario_id"] == "S-REPLAY"
    assert trace["event_type"] == "SUPPLIER_DISRUPTION"
    assert trace["data_source_label"] == "simulated"


def test_trace_chain_is_complete_and_ordered():
    run = run_replay_for(_arms())
    trace = run["results"][1].traceability["entities"][0]
    assert trace["chain"] == CHAIN


def test_trace_records_decision_assumptions_text():
    run = run_replay_for(_arms())
    expedite = next(r for r in run["results"] if r.decision_type == "EXPEDITE_INBOUND")
    assumptions = expedite.traceability["entities"][0]["decision_assumptions"]
    assert any("decision assumption" in note for note in assumptions)
    assert any("Expedited inbound arrives earlier." in note for note in assumptions)


def test_baseline_ref_helper_matches_reported_reference():
    from backend.app.tests.replay_support import make_scenario

    scenario = make_scenario()
    assert traceability.baseline_ref(scenario) == "baseline:S-REPLAY"


def test_effect_notes_record_decision_transform():
    run = run_replay_for(_arms())
    expedite = next(r for r in run["results"] if r.decision_type == "EXPEDITE_INBOUND")
    assert any("EXPEDITE_INBOUND applied" in note for note in expedite.effect_notes)
    assert any("decision assumption" in note for note in expedite.effect_notes)
    control = next(r for r in run["results"] if r.decision_type == "NO_ACTION")
    assert any("NO_ACTION" in note for note in control.effect_notes)
