"""Phase 10 reporting-contract tests (spec section 25.I).

Exactly 21 sections, honest status language, banned-word scan, labels,
and Markdown rendering. All report content is SYNTHETIC / simulated.
"""

from __future__ import annotations

import json
import re

from backend.app.analytics.optimization import (
    OBJECTIVES,
    REPORT_SECTIONS,
    SECTION_TITLES,
    STATUSES,
    OptimizationConfig,
    build_report,
    render_markdown,
)
from backend.app.tests.optimization_support import (
    build_case,
    run_case,
    short_outage_scenario,
)

BANNED_PATTERN = re.compile(
    r"\b(best|should|recommend|ideal|perfect)\b", re.IGNORECASE
)

OBJECTIVE = OptimizationConfig(objective="minimize_total_cost")


def _report(config=None, case=None):
    run = run_case(config=config or OBJECTIVE,
                   case=case or build_case(short_outage_scenario()))
    return run, build_report(run)


def test_report_contains_exactly_the_21_declared_sections():
    _, report = _report()
    assert len(REPORT_SECTIONS) == 21
    assert report["sections"] == list(REPORT_SECTIONS)
    for section in REPORT_SECTIONS:
        assert section in report, section
    assert report["report_type"] == "optimization"


def test_section_titles_cover_every_section():
    assert set(SECTION_TITLES) == set(REPORT_SECTIONS)
    for title in SECTION_TITLES.values():
        assert title[0].isupper()


def test_markdown_renders_every_section_with_numbered_heading():
    _, report = _report()
    markdown = render_markdown(report)
    assert markdown.startswith("# Optimization Run Report (Synthetic / Simulated Data)")
    for position, section in enumerate(REPORT_SECTIONS, start=1):
        heading = f"## {position}. {SECTION_TITLES[section]}"
        assert heading in markdown, heading
    assert markdown.endswith("\n")


def test_banned_wording_is_absent_from_json_and_markdown():
    _, report = _report()
    payload = json.dumps(report, default=str)
    assert BANNED_PATTERN.search(payload) is None
    markdown = render_markdown(report)
    assert BANNED_PATTERN.search(markdown) is None


def test_banned_wording_is_absent_for_infeasible_report():
    run, report = _report(case=build_case())
    assert run["result"]["status"] == "INFEASIBLE"
    payload = json.dumps(report, default=str)
    assert BANNED_PATTERN.search(payload) is None
    markdown = render_markdown(report)
    assert BANNED_PATTERN.search(markdown) is None


def test_feasible_report_states_status_objective_and_checks():
    _, report = _report()
    feasibility = report["feasibility_status"]
    assert feasibility["status"] == "OPTIMAL"
    assert feasibility["feasible"] is True
    assert feasibility["solver"] == "scipy-milp-highs"
    checks = {item["name"]: item["status"]
              for item in feasibility["validation_checks"]}
    assert len(checks) == 7
    assert all(status == "PASS" for status in checks.values())
    value = report["objective_value"]
    assert value["value"] == 4500.0
    assert value["status"] == "OPTIMAL"
    assert "optimum of the declared objective" in value["statement"]
    assert report["objective"]["name"] == "minimize_total_cost"
    assert report["objective"]["direction"] == "minimize"


def test_infeasible_report_explains_status_honestly():
    _, report = _report(case=build_case())
    feasibility = report["feasibility_status"]
    assert feasibility["status"] == "INFEASIBLE"
    assert "no feasible solution" in feasibility["note"]
    assert feasibility["structural_diagnostics"]
    value = report["objective_value"]
    assert value["value"] is None
    assert "No objective value for status INFEASIBLE" in value["statement"]
    decisions = report["decision_values"]
    assert decisions["count"] == 0
    assert decisions["note"] == "No decision values for status INFEASIBLE."
    assert report["objective_breakdown"]["total_procurement_cost"] is None


def test_decision_values_section_counts_only_nonzero_orders():
    _, report = _report()
    decisions = report["decision_values"]
    assert decisions["count"] == 2
    assert decisions["units"] == "demand_units"
    assert all(value > 0 for value in decisions["values"].values())
    assert all(name.startswith("order[") for name in decisions["values"])
    assert "MOQ selectors are internal and excluded" in decisions["note"]


def test_no_data_report_is_complete_and_labelled():
    run = run_case(case=build_case(short_outage_scenario()), product_id="NOPE")
    report = build_report(run)
    assert report["feasibility_status"]["status"] == "NO_DATA"
    assert report["decision_values"]["count"] == 0
    assert report["synthetic"] is True
    assert report["data_source_label"] == "simulated"


def test_binding_constraints_grouped_by_business_type():
    _, report = _report()
    binding = report["binding_constraints"]
    assert binding["count"] >= 1
    assert "demand_satisfaction" in binding["by_type"]
    assert not any(name.startswith("daily_") for name in binding["names"])
    assert "definitional" in binding["note"]


def test_slack_utilization_section_present_with_note():
    _, report = _report()
    utilization = report["slack_utilization"]
    assert "slack" in utilization
    assert "ceiling_utilization" in utilization
    assert "fully consumed" in utilization["note"]


def test_assumptions_section_lists_adapter_assumptions():
    _, report = _report()
    assumptions = report["assumptions"]
    assert assumptions
    joined = " ".join(assumptions)
    assert "point parameters" in joined
    assert "lead_time_days" in joined


def test_metadata_section_declares_ids_config_and_timings():
    run, report = _report()
    metadata = report["optimization_run_metadata"]
    assert metadata["optimization_id"] == run["problem"]["problem_id"]
    assert metadata["replay_id"] == run["replay_id"]
    assert metadata["objective_key"] in OBJECTIVES
    assert metadata["solver_status"] in STATUSES
    assert set(metadata["timings_seconds"]) >= {
        "input_preparation", "problem_construction", "solver",
        "result_validation", "total",
    }
    assert metadata["config"]["objective"] == "minimize_total_cost"
    assert metadata["synthetic"] is True


def test_markdown_is_deterministic_for_identical_payloads():
    run, report = _report()
    assert render_markdown(report) == render_markdown(report)


def test_every_objective_renders_full_report():
    for key in OBJECTIVES:
        config = OptimizationConfig(
            objective=key,
            shortage_penalty_per_unit=10.0 if key == "cost_shortage_tradeoff" else None,
        )
        _, report = _report(config=config)
        assert report["sections"] == list(REPORT_SECTIONS)
        payload = json.dumps(report, default=str)
        assert BANNED_PATTERN.search(payload) is None
