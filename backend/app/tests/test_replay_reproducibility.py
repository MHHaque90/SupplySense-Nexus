"""Phase 9 reproducibility tests (same inputs + seed → identical replay)."""

from backend.app.analytics.replay import decisions, reports
from backend.app.analytics.simulation import runner as runner_mod
from backend.app.analytics.simulation.types import DEFAULT_SIMULATION_CONFIG
from backend.app.tests.replay_support import (
    ANALYSIS_DATE,
    make_inputs,
    make_scenario,
    run_replay_for,
)


def _arms(replay_id: str = "replay-S-REPLAY"):
    return [
        decisions.build_no_action(replay_id),
        decisions.build_decision(
            replay_id, "EXPEDITE_INBOUND",
            affected_suppliers=["S1"], affected_products=["P1"],
            affected_warehouses=["W1"],
            quantities={"expedite_units": 30.0},
            timing={"start_day": 0, "end_day": 14, "delay_reduction_days": 3},
            cost_assumptions={"expedite_cost": 500.0},
        ),
        decisions.build_decision(
            replay_id, "INVENTORY_TRANSFER",
            affected_products=["P1"], affected_warehouses=["W1", "W2"],
            quantities={"transfer_units": 15.0},
        ),
    ]


def test_identical_inputs_seed_and_count_reproduce_results():
    scenario = make_scenario()
    inputs = make_inputs()
    first = run_replay_for(_arms(), scenario, inputs)
    second = run_replay_for(_arms(), scenario, inputs)
    assert [r.to_dict() for r in first["results"]] == [
        r.to_dict() for r in second["results"]
    ]
    assert first["sample_fingerprint"] == second["sample_fingerprint"]
    assert first["baseline"].to_dict() == second["baseline"].to_dict()
    assert first["pairwise"] == second["pairwise"]


def test_no_action_reproduces_phase8_scenario_outcome():
    scenario = make_scenario()
    inputs = make_inputs()
    phase8 = runner_mod.run_scenario(
        scenario, inputs["forecasts"], inputs["snapshots"], inputs["shipments"],
        inputs["po_lines"], inputs["supplier_links"], ANALYSIS_DATE,
        DEFAULT_SIMULATION_CONFIG,
    )
    control = decisions.build_no_action("replay-S-REPLAY")
    run = run_replay_for([control], scenario, inputs)
    arm = next(r for r in run["results"] if r.decision_type == "NO_ACTION")
    phase8_outcome = phase8["scenario"].to_dict()
    arm_outcome = dict(arm.outcome)
    phase8_outcome.pop("label", None)
    arm_outcome.pop("label", None)
    assert arm_outcome == phase8_outcome


def test_replay_report_is_reproducible():
    scenario = make_scenario()
    inputs = make_inputs()
    first = reports.build_report(run_replay_for(_arms(), scenario, inputs))
    second = reports.build_report(run_replay_for(_arms(), scenario, inputs))
    assert first == second
    assert reports.render_markdown(first) == reports.render_markdown(second)


def test_changing_the_seed_changes_simulation_variability():
    inputs = make_inputs()
    first = run_replay_for(_arms(), make_scenario(random_seed=7), inputs)
    second = run_replay_for(_arms(), make_scenario(random_seed=99), inputs)
    assert first["sample_fingerprint"] != second["sample_fingerprint"]
    assert first["uncertainty"]["simulation_variability"]["random_seed"] == 7
    assert second["uncertainty"]["simulation_variability"]["random_seed"] == 99


def test_changing_simulation_count_changes_results_metadata():
    inputs = make_inputs()
    few = run_replay_for(_arms(), make_scenario(simulation_count=3), inputs)
    many = run_replay_for(_arms(), make_scenario(simulation_count=9), inputs)
    assert few["sample_fingerprint"] != many["sample_fingerprint"]
    assert few["scenario"]["simulation_count"] == 3
    assert many["scenario"]["simulation_count"] == 9


def test_replay_id_is_deterministic():
    scenario = make_scenario()
    assert replay_id_of(scenario) == replay_id_of(scenario)
    assert replay_id_of(scenario) == "replay-S-REPLAY"
    from backend.app.analytics.replay import replay as replay_mod

    assert replay_mod.resolve_replay_id(scenario, "custom") == "custom"


def replay_id_of(scenario):
    from backend.app.analytics.replay import replay as replay_mod

    return replay_mod.resolve_replay_id(scenario)
