"""Phase 10 determinism tests (spec section 25.G).

Identical inputs must produce byte-identical payloads (timings excepted),
identical problem ids, identical reports, and identical Markdown.
All data is SYNTHETIC.
"""

from __future__ import annotations

import copy
import json

import numpy as np

from backend.app.analytics.optimization import OptimizationConfig, build_report, render_markdown
from backend.app.analytics.optimization import inputs as inputs_mod
from backend.app.analytics.optimization import problem as problem_mod
from backend.app.tests.optimization_support import (
    build_case,
    run_case,
    short_outage_scenario,
)

OBJECTIVE = OptimizationConfig(objective="minimize_total_cost")


def _without_timings(run: dict) -> dict:
    cleaned = copy.deepcopy(run)
    cleaned.pop("timings", None)
    return cleaned


def _normalized_report(run: dict) -> dict:
    payload = copy.deepcopy(run)
    payload["timings"] = {}
    report = build_report(payload)
    report["optimization_run_metadata"]["timings_seconds"] = {}
    return report


def test_two_runs_are_identical_excluding_timings():
    first = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    second = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    assert json.dumps(_without_timings(first), sort_keys=True, default=str) == (
        json.dumps(_without_timings(second), sort_keys=True, default=str)
    )


def test_problem_id_and_decisions_stable_across_runs():
    first = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    second = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    assert first["problem"]["problem_id"] == second["problem"]["problem_id"]
    assert first["result"]["decision_values"] == second["result"]["decision_values"]
    assert list(first["result"]["decision_values"]) == list(
        second["result"]["decision_values"]
    )


def test_reports_are_byte_identical_excluding_timings():
    first = _normalized_report(
        run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    )
    second = _normalized_report(
        run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    )
    assert json.dumps(first, sort_keys=True, default=str) == (
        json.dumps(second, sort_keys=True, default=str)
    )
    assert render_markdown(first) == render_markdown(second)


def test_formulation_matrices_are_reproducible():
    case = build_case(short_outage_scenario())
    inputs = inputs_mod.build_optimization_inputs(
        case["run"], case["entities"], case["inputs"]["supplier_links"],
    )
    first = problem_mod.build_formulation(inputs, OBJECTIVE)
    second = problem_mod.build_formulation(inputs, OBJECTIVE)
    assert np.array_equal(first.constraint_matrix, second.constraint_matrix)
    assert np.array_equal(first.objective_vector, second.objective_vector)
    assert first.variable_names == second.variable_names
    assert [row.to_dict() for row in first.rows] == [
        row.to_dict() for row in second.rows
    ]


def test_objective_value_is_stable_across_runs():
    first = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    second = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    assert first["result"]["objective_value"] == second["result"]["objective_value"]
    assert first["result"]["objective_breakdown"] == second["result"][
        "objective_breakdown"
    ]
    assert first["result"]["binding_constraints"] == second["result"][
        "binding_constraints"
    ]


def test_timing_values_are_the_only_nondeterministic_payload_keys():
    first = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    second = run_case(config=OBJECTIVE, case=build_case(short_outage_scenario()))
    diffs = [
        key for key in first
        if key != "timings" and json.dumps(
            first[key], sort_keys=True, default=str
        ) != json.dumps(second[key], sort_keys=True, default=str)
    ]
    assert diffs == []
    assert first["timings"] != {} or second["timings"] != {}
