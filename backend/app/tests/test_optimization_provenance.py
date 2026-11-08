"""Phase 10 provenance, labeling, and honesty tests (spec section 25.G).

Every output must carry explicit lineage to Phase 9, declare synthetic
/ simulated labeling, and disclose warnings instead of inventing data.
All data here is SYNTHETIC.
"""

from __future__ import annotations

from backend.app.analytics.optimization import OptimizationConfig, build_report
from backend.app.tests.optimization_support import (
    build_case,
    run_case,
    short_outage_scenario,
)

OBJECTIVE = OptimizationConfig(objective="minimize_total_cost")


def test_run_payload_carries_full_phase9_lineage():
    run = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    provenance = run["problem"]["provenance"]
    assert provenance["source_phase"] == "phase_9_decision_replay"
    assert provenance["source_module"] == "backend.app.analytics.replay"
    assert provenance["replay_id"].startswith("replay-")
    assert provenance["scenario_fingerprint"]
    assert provenance["baseline_ref"]
    assert provenance["sample_fingerprint"]
    assert provenance["synthetic"] is True
    assert provenance["data_source_label"] == "simulated"
    assert run["optimization_id"] == run["problem"]["problem_id"]
    assert run["replay_id"] == provenance["replay_id"]


def test_forecast_references_carry_model_metadata():
    run = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    references = run["problem"]["provenance"]["forecast_references"]
    assert references
    for reference in references:
        assert reference["model_name"] == "synthetic-forecast"
        assert reference["origin"]
        assert reference["product_id"] and reference["warehouse_id"]


def test_run_and_report_declare_simulated_labeling():
    run = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    assert run["synthetic"] is True
    assert run["data_source_label"] == "simulated"
    report = build_report(run)
    assert report["synthetic"] is True
    assert report["data_source_label"] == "simulated"
    disclaimer = report["synthetic_data_disclaimer"]
    assert disclaimer["data_source_label"] == "simulated"
    assert "synthetic" in disclaimer["statement"].lower()
    assert report["optimization_run_metadata"]["synthetic"] is True


def test_report_provenance_matches_problem_provenance():
    run = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    report = build_report(run)
    assert report["provenance"] == run["problem"]["provenance"]


def test_or_tools_deviation_and_limitations_are_disclosed():
    run = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    report = build_report(run)
    limitations = " ".join(report["limitations"])
    assert "OR-Tools" in limitations
    assert "not re-simulated" in limitations
    assert "no Pareto-front" in limitations
    assert "docs/optimization-engine.md" in limitations
    solver_note = report["solver_information"]["backend_note"]
    assert "no new dependency" in solver_note
    assert "OR-Tools" in solver_note


def test_warnings_are_merged_once_into_report():
    case = build_case(short_outage_scenario())
    run = run_case(config=OBJECTIVE, case=case)
    report = build_report(run)
    warnings = report["warnings"]
    unchecked = [item for item in warnings if item.startswith("UNCHECKED:")]
    assert unchecked
    assert len(warnings) == len(set(warnings))
    assert all(not item.startswith("UNCHECKED:") or "invented" not in item
               for item in warnings)


def test_missing_capacity_is_disclosed_not_invented():
    run = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    report = build_report(run)
    warnings = " ".join(report["warnings"])
    assert "capacity constraint not enforced" in warnings
    constraint_names = [
        item["name"] for item in report["constraints"]["declared"]
    ]
    assert not any(name.startswith("supplier_capacity:S1") for name in constraint_names)


def test_uncertainty_section_discloses_interval_treatment():
    run = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    report = build_report(run)
    intervals = report["uncertainty"]["requirement_intervals"]
    assert intervals["lower_upper_disclosed"] is True
    assert intervals["bounds_source"] == (
        "phase4_intervals_adjusted_by_scenario_point_parameters"
    )
    assert "not optimized" in intervals["note"]


def test_scenario_section_declares_event_and_simulation_settings():
    run = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    report = build_report(run)
    scenario_section = report["source_scenario"]
    assert scenario_section["event"]["event_type"] == "SUPPLIER_DISRUPTION"
    assert scenario_section["event"]["duration_days"] == 3
    assert scenario_section["scenario_id"] == "S-SHORT"
    assert scenario_section["analysis_date"]
    assert scenario_section["data_source_label"] == "simulated"
