"""Phase 9 report contract tests (exactly 21 sections, labels, Markdown)."""

import json

from backend.app.analytics.replay import decisions, reports
from backend.app.tests.replay_support import run_replay_for


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
    ]


def _report():
    run = run_replay_for(_arms())
    return reports.build_report(run), run


def test_report_sections_are_exactly_twenty_one():
    assert len(reports.REPORT_SECTIONS) == 21
    assert len(set(reports.REPORT_SECTIONS)) == 21
    assert set(reports.SECTION_TITLES) == set(reports.REPORT_SECTIONS)


def test_build_report_returns_all_sections_and_no_extras():
    report, _ = _report()
    assert set(report) == set(reports.REPORT_SECTIONS)


def test_metadata_is_labeled_simulated():
    report, _ = _report()
    metadata = report["replay_metadata"]
    assert metadata["synthetic"] is True
    assert metadata["data_source_label"] == "simulated"
    assert metadata["decision_count"] == 2
    assert report["synthetic_data_disclaimer"]


def test_decision_definitions_labeled_decision_assumption():
    report, _ = _report()
    assert report["decision_definitions"]
    for item in report["decision_definitions"]:
        assert item["data_label"] == "DECISION_ASSUMPTION"
        assert item["source"] in ("user_defined", "generated")


def test_cost_sections_preserve_none_and_provenance_labels():
    report, _ = _report()
    for item in report["cost_outcomes"].values():
        assert set(item) == {
            "decision_cost", "disruption_cost", "total_modeled_cost", "note",
        }
    labels = {
        note
        for item in report["cost_assumptions"].values()
        for note in item["notes"].values()
    }
    assert "USER_ASSUMED_COST" in labels
    assert "OBSERVED_PURCHASE_COST" in labels


def test_limitations_state_no_ranking_and_no_optimization():
    report, _ = _report()
    text = " ".join(report["limitations"])
    assert "never ranks, never recommends" in text
    assert "Phase 9 does not optimize" in text
    assert "SYNTHETIC DATA" in text
    assert report["phase_10_handoff"]


def test_markdown_renders_all_sections_in_order():
    report, _ = _report()
    markdown = reports.render_markdown(report)
    headings = [line for line in markdown.splitlines() if line.startswith("## ")]
    assert len(headings) == 21
    for index, section in enumerate(reports.REPORT_SECTIONS, start=1):
        expected = f"## {index}. {reports.SECTION_TITLES[section]}"
        assert headings[index - 1] == expected
    assert markdown.startswith("# SupplySense Nexus Decision Replay Lab Report")


def test_report_is_json_serializable_for_cli_output():
    report, _ = _report()
    payload = json.dumps(report, default=str)
    assert '"data_source_label": "simulated"' in payload
