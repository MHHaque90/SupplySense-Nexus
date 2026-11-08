"""Phase 9 no-ranking language and structure tests.

Phase 9 performs factual decision comparison only. Nothing in the run
dictionary, the report, or the rendered Markdown may rank, recommend,
score, or select a decision.
"""

import json

from backend.app.analytics.replay import decisions, reports
from backend.app.tests.replay_support import run_replay_for

BANNED_KEYS = {
    "rank", "ranks", "ranked", "ranking",
    "recommend", "recommends", "recommended", "recommendation",
    "confidence", "score", "scores", "scoring",
    "winner", "best", "optimal", "optimum", "optimization",
    "preferred", "preference", "tier", "priority",
    "recommended_option", "selected_option",
}

BANNED_HEADING_WORDS = ("rank", "recommend", "optimal", "score", "best")


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
        decisions.build_decision(
            replay_id, "DEMAND_ADJUSTMENT",
            affected_products=["P1"], affected_warehouses=["W1"],
            quantities={"demand_multiplier": 0.9},
            timing={"start_day": 0, "end_day": 14},
        ),
    ]


def _walk_keys(node):
    """Yield every mapping key in a nested JSON-like structure."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _walk_keys(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk_keys(item)


def _run_and_report():
    run = run_replay_for(_arms())
    return run, reports.build_report(run)


def test_run_dict_contains_no_ranking_keys():
    run, _ = _run_and_report()
    for key in _walk_keys(run):
        assert key.lower() not in BANNED_KEYS, f"banned key in run: {key}"


def test_report_contains_no_ranking_keys():
    _, report = _run_and_report()
    for key in _walk_keys(report):
        assert key.lower() not in BANNED_KEYS, f"banned key in report: {key}"


def test_results_carry_no_confidence_or_score_fields():
    run, _ = _run_and_report()
    for result in run["results"]:
        for key in result.to_dict():
            assert key.lower() not in BANNED_KEYS


def test_markdown_headings_never_rank_or_recommend():
    _, report = _run_and_report()
    markdown = reports.render_markdown(report)
    headings = [line for line in markdown.splitlines() if line.startswith("## ")]
    assert headings
    for heading in headings:
        lowered = heading.lower()
        for banned in BANNED_HEADING_WORDS:
            assert banned not in lowered, f"banned word in heading: {heading}"


def test_pairwise_semantics_state_no_ranking_or_selection():
    run, report = _run_and_report()
    assert run["pairwise"]
    for pair in run["pairwise"]:
        assert "no ranking or recommendation" in pair["semantics"]
    comparison = report["decision_to_decision_comparison"]
    assert "no ranking, no scores, no selection" in comparison["semantics"]


def test_required_no_ranking_statements_are_present():
    _, report = _run_and_report()
    limitations = " ".join(report["limitations"])
    assert "never ranks, never recommends, never scores" in limitations
    assert "Phase 9 does not optimize" in limitations
    handoff = " ".join(report["phase_10_handoff"])
    assert "No optimization API is defined here" in handoff


def test_run_json_never_mentions_recommended_or_ranked_fields():
    run, report = _run_and_report()
    banned_json_phrases = (
        '"recommended_option"', '"ranked_options"', '"ranking":',
        '"confidence":', '"score":',
    )
    for payload in (json.dumps(run, default=str), json.dumps(report, default=str)):
        for phrase in banned_json_phrases:
            assert phrase not in payload, phrase
