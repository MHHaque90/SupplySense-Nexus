"""Phase 9 uncertainty separation tests (four categories, never merged)."""

from backend.app.analytics.replay import decisions, reports
from backend.app.tests.replay_support import run_replay_for

CATEGORIES = {
    "forecast_uncertainty",
    "scenario_uncertainty",
    "simulation_variability",
    "decision_uncertainty",
}


def _arms(replay_id: str = "replay-S-REPLAY"):
    return [
        decisions.build_no_action(replay_id),
        decisions.build_decision(
            replay_id, "EXPEDITE_INBOUND",
            affected_suppliers=["S1"], affected_products=["P1"],
            affected_warehouses=["W1"],
            quantities={"expedite_units": 30.0},
            timing={"start_day": 0, "end_day": 14, "delay_reduction_days": 3},
        ),
    ]


def test_four_categories_stay_separate():
    run = run_replay_for(_arms())
    assert set(run["uncertainty"]) == CATEGORIES


def test_every_category_is_a_documented_note_not_a_score():
    run = run_replay_for(_arms())
    for category, payload in run["uncertainty"].items():
        assert isinstance(payload, dict), category
        assert "note" in payload, category
        assert isinstance(payload["note"], str) and payload["note"], category
        for key in payload:
            assert "score" not in key and "index" not in key, f"{category}.{key}"


def test_forecast_uncertainty_inherited_not_recalculated():
    run = run_replay_for(_arms())
    forecast = run["uncertainty"]["forecast_uncertainty"]
    assert forecast["source"] == "phase4_intervals"
    assert forecast["recalculated"] is False
    assert "not recalculated by replay" in forecast["note"]


def test_scenario_uncertainty_covers_event_distributions_only():
    run = run_replay_for(_arms())
    scenario_uncertainty = run["uncertainty"]["scenario_uncertainty"]
    assert isinstance(scenario_uncertainty["distributions"], list)
    assert "event probability" in scenario_uncertainty["note"]


def test_simulation_variability_records_seed_count_and_fingerprint():
    run = run_replay_for(_arms())
    variability = run["uncertainty"]["simulation_variability"]
    assert variability["random_seed"] == 7
    assert variability["simulation_count"] == 5
    assert variability["sample_fingerprint"] == run["sample_fingerprint"]
    assert "reused by every arm" in variability["note"]


def test_decision_uncertainty_lists_each_decision_with_own_assumptions():
    run = run_replay_for(_arms())
    decision_layer = run["uncertainty"]["decision_uncertainty"]
    assert len(decision_layer["decisions"]) == len(_arms())
    for item in decision_layer["decisions"]:
        assert set(item) == {
            "decision_id", "decision_type", "quantities", "timing",
            "cost_assumptions",
        }
    assert "never merged with forecast, scenario, or simulation uncertainty" \
        in decision_layer["note"]


def test_report_uncertainty_section_matches_run_and_renders():
    run = run_replay_for(_arms())
    report = reports.build_report(run)
    assert report["uncertainty"] == run["uncertainty"]
    markdown = reports.render_markdown(report)
    assert "- forecast uncertainty:" in markdown
    assert "- scenario uncertainty:" in markdown
    assert "- simulation variability:" in markdown
    assert "- decision uncertainty:" in markdown
