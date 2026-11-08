"""Phase 9 shared-baseline tests (built once, shared, never mutated)."""

from backend.app.analytics.replay import decisions
from backend.app.analytics.simulation import runner as runner_mod
from backend.app.analytics.simulation.types import DEFAULT_SIMULATION_CONFIG
from backend.app.tests.replay_support import (
    ANALYSIS_DATE,
    make_inputs,
    make_scenario,
    run_replay_for,
)


def _decision_list(replay_id: str):
    expedite = decisions.build_decision(
        replay_id, "EXPEDITE_INBOUND",
        affected_suppliers=["S1"], affected_products=["P1"],
        affected_warehouses=["W1"],
        quantities={"expedite_units": 30.0},
        timing={"start_day": 0, "end_day": 14, "delay_reduction_days": 3},
    )
    return [decisions.build_no_action(replay_id), expedite]


def test_baseline_built_once_and_shared_across_decisions():
    scenario = make_scenario()
    inputs = make_inputs()
    single = run_replay_for(
        [decisions.build_no_action("replay-S-REPLAY")], scenario, inputs
    )
    multi = run_replay_for(_decision_list(scenario.scenario_id), scenario, inputs)
    assert single["baseline"].to_dict() == multi["baseline"].to_dict()


def test_every_arm_references_the_same_baseline():
    run = run_replay_for(_decision_list("replay-S-REPLAY"))
    refs = {
        trace["baseline_ref"]
        for result in run["results"]
        for trace in result.traceability["entities"]
    }
    assert refs == {"baseline:S-REPLAY"}
    assert run["baseline_ref"] == "baseline:S-REPLAY"


def test_baseline_label_is_baseline_and_not_an_arm():
    run = run_replay_for(_decision_list("replay-S-REPLAY"))
    assert run["baseline"].label == "baseline"
    assert all(result.outcome["label"] == "decision" for result in run["results"])


def test_baseline_matches_phase8_baseline():
    scenario = make_scenario()
    inputs = make_inputs()
    phase8 = runner_mod.run_scenario(
        scenario, inputs["forecasts"], inputs["snapshots"], inputs["shipments"],
        inputs["po_lines"], inputs["supplier_links"], ANALYSIS_DATE,
        DEFAULT_SIMULATION_CONFIG,
    )
    run = run_replay_for(
        [decisions.build_no_action("replay-S-REPLAY")], scenario, inputs
    )
    assert run["baseline"].to_dict() == phase8["baseline"].to_dict()


def test_no_action_deltas_match_phase8_deltas():
    scenario = make_scenario()
    inputs = make_inputs()
    phase8 = runner_mod.run_scenario(
        scenario, inputs["forecasts"], inputs["snapshots"], inputs["shipments"],
        inputs["po_lines"], inputs["supplier_links"], ANALYSIS_DATE,
        DEFAULT_SIMULATION_CONFIG,
    )
    control = decisions.build_no_action("replay-S-REPLAY")
    run = run_replay_for([control], scenario, inputs)
    assert run["baseline_deltas"][control.decision_id] == phase8["deltas"]
    assert all(
        value is not None for value in run["baseline_deltas"][control.decision_id].values()
    )


def test_decision_arms_do_not_modify_the_shared_baseline():
    scenario = make_scenario()
    inputs = make_inputs()
    before = run_replay_for(
        [decisions.build_no_action("replay-S-REPLAY")], scenario, inputs
    )["baseline"].to_dict()
    transfer = decisions.build_decision(
        "replay-S-REPLAY", "INVENTORY_TRANSFER",
        affected_products=["P1"], affected_warehouses=["W1", "W2"],
        quantities={"transfer_units": 15.0},
    )
    after = run_replay_for(
        [decisions.build_no_action("replay-S-REPLAY"), transfer], scenario, inputs
    )
    assert after["baseline"].to_dict() == before
    # The transfer arm still produced its own separate simulated outcome.
    control = next(r for r in after["results"] if r.decision_type == "NO_ACTION")
    moved = next(r for r in after["results"] if r.decision_type == "INVENTORY_TRANSFER")
    assert moved.outcome["expected_stockout_days"] != control.outcome[
        "expected_stockout_days"
    ]


def test_scenario_is_never_mutated_by_replay():
    scenario = make_scenario()
    snapshot = scenario.to_dict()
    run = run_replay_for(_decision_list("replay-S-REPLAY"), scenario)
    assert scenario.to_dict() == snapshot
    assert run["scenario"] == snapshot
    assert run["scenario_fingerprint"]["scenario_id"] == "S-REPLAY"
    assert run["scenario_fingerprint"]["random_seed"] == scenario.random_seed
    assert run["scenario_fingerprint"]["horizon_days"] == scenario.horizon_days
