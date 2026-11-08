"""Optimization reporting contract (Phase 10).

JSON + Markdown reports with exactly the 21 sections required by the
optimization-engine specification (``REPORT_SECTIONS``). Rendered prose never
uses "best", "recommend", "should", "ideal", or "perfect" wording; solver
status, feasibility, objective, constraints, assumptions, provenance,
uncertainty, warnings, and limitations are always stated explicitly.

All report content is SYNTHETIC / simulated planning data.
"""

from __future__ import annotations

from typing import Any

from backend.app.analytics import SYNTHETIC_ANALYTICS_DISCLAIMER

REPORT_SECTIONS = (
    "synthetic_data_disclaimer",
    "optimization_run_metadata",
    "source_scenario",
    "problem_definition",
    "objective",
    "decision_variables",
    "constraints",
    "assumptions",
    "solver_information",
    "feasibility_status",
    "objective_value",
    "objective_breakdown",
    "decision_values",
    "baseline_comparison",
    "scenario_comparison",
    "binding_constraints",
    "slack_utilization",
    "provenance",
    "uncertainty",
    "warnings",
    "limitations",
)

SECTION_TITLES = {
    "synthetic_data_disclaimer": "Synthetic Data Disclaimer",
    "optimization_run_metadata": "Optimization Run Metadata",
    "source_scenario": "Source Scenario",
    "problem_definition": "Problem Definition",
    "objective": "Objective",
    "decision_variables": "Decision Variables",
    "constraints": "Constraints",
    "assumptions": "Assumptions",
    "solver_information": "Solver Information",
    "feasibility_status": "Feasibility Status",
    "objective_value": "Objective Value",
    "objective_breakdown": "Objective Breakdown",
    "decision_values": "Decision Values",
    "baseline_comparison": "Baseline Comparison",
    "scenario_comparison": "Scenario Comparison",
    "binding_constraints": "Binding Constraints",
    "slack_utilization": "Slack and Utilization",
    "provenance": "Provenance",
    "uncertainty": "Uncertainty",
    "warnings": "Warnings",
    "limitations": "Limitations",
}

_FIXED_LIMITATIONS = (
    "The optimized plan is evaluated with deterministic point accounting only; "
    "it is not re-simulated through Phase 9 Monte Carlo machinery.",
    "Orders arriving after the horizon are out of scope (excluded with reason).",
    "Scenario effects on new orders use the event's declared point parameters; "
    "configured distributions are disclosed but not resampled.",
    "One explicit scalar objective per run; no Pareto-front generation.",
    "Solver backend is SciPy/HiGHS (bundled dependency); the roadmap's "
    "OR-Tools option is an uninstalled optional extra — see "
    "docs/optimization-engine.md.",
)


def _binding_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Group binding rows by declared constraint type."""
    names = list(result.get("binding_constraints", []))
    by_type: dict[str, list[str]] = {}
    for name in names:
        row_type = name.split(":")[0]
        by_type.setdefault(row_type, []).append(name)
    return {
        "count": len(names),
        "by_type": {key: sorted(value) for key, value in sorted(by_type.items())},
        "names": names,
        "note": (
            "Daily accounting identities (daily_balance rows) are definitional "
            "and excluded from this listing; business constraints are listed."
        ),
    }


def _utilization(result: dict[str, Any]) -> dict[str, Any]:
    """Ceiling utilization for capacity/budget rows with a positive bound."""
    slack = dict(result.get("slack", {}))
    problem = result.get("problem", {})
    utilization: dict[str, float] = {}
    for constraint in problem.get("constraints", []):
        name = constraint.get("name", "")
        bound = constraint.get("bound")
        if constraint.get("type") not in ("supplier_capacity", "budget"):
            continue
        if bound is None or bound <= 0 or name not in slack:
            continue
        used = float(bound) - float(slack[name])
        utilization[name] = round(max(0.0, min(1.0, used / float(bound))), 6)
    return {
        "slack": slack,
        "ceiling_utilization": utilization,
        "note": (
            "Ceiling utilization = (bound - slack) / bound for capacity and "
            "budget rows with a positive declared bound; 1.0 means the ceiling "
            "is fully consumed by the solution."
        ),
    }


def build_report(run: dict[str, Any]) -> dict[str, Any]:
    """Build the 21-section optimization report from one run payload."""
    problem = run["problem"]
    result = run["result"]
    scenario = run["scenario"]
    parameters = problem["parameters"]
    objective = problem["objective"]
    event = scenario.get("event")
    diagnostics = list(run.get("diagnostics", []))
    status = result["status"]
    checks = list(run.get("checks", []))
    warnings = list(result.get("warnings", []))
    for item in run.get("input_warnings", []):
        if item not in warnings:
            warnings.append(item)
    for item in run.get("validation_warnings", []):
        if item not in warnings:
            warnings.append(item)

    feasibility: dict[str, Any] = {
        "status": status,
        "feasible": result["feasible"],
        "solver": result["solver"],
        "solver_version": result["solver_version"],
        "validation_checks": checks,
        "structural_diagnostics": diagnostics,
        "note": (
            "Status is the solver's feasibility state for the declared problem; "
            "validation_checks are independent re-derivations from the "
            "extracted solution and the Phase 8 daily engine."
        ),
    }
    if status == "INFEASIBLE":
        feasibility["note"] = (
            "The declared problem has no feasible solution under its hard "
            "constraints; structural_diagnostics lists the structural causes "
            "identified (a full conflict set is unavailable from this backend)."
        )

    objective_value: dict[str, Any] = {
        "value": result.get("objective_value"),
        "units": objective["units"],
        "direction": objective["direction"],
        "status": status,
    }
    if result.get("objective_value") is None:
        objective_value["statement"] = (
            f"No objective value for status {status}; no solution vector was "
            "produced."
        )
    else:
        objective_value["statement"] = (
            f"Status {status}: the value is the "
            f"{'optimum' if status == 'OPTIMAL' else 'attained value'} of the "
            f"declared objective under the declared constraints."
        )

    decision_values = result.get("decision_values", {})
    binding = _binding_summary(result)

    report: dict[str, Any] = {
        "report_type": "optimization",
        "sections": list(REPORT_SECTIONS),
        "synthetic": True,
        "data_source_label": "simulated",
        "synthetic_data_disclaimer": {
            "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER,
            "data_source_label": "simulated",
            "statement": (
                "Every value in this report is a synthetic, simulated planning "
                "output; none of it represents actual company performance or "
                "procurement execution."
            ),
        },
        "optimization_run_metadata": {
            "optimization_id": run["optimization_id"],
            "replay_id": run["replay_id"],
            "scenario_id": run["scenario_id"],
            "analysis_date": problem["analysis_date"],
            "horizon_days": problem["horizon"],
            "objective_key": objective["name"],
            "solver": result["solver"],
            "solver_status": status,
            "timings_seconds": run.get("timings", {}),
            "config": run.get("config", {}),
            "synthetic": True,
            "data_source_label": "simulated",
        },
        "source_scenario": {
            "scenario_id": scenario.get("scenario_id"),
            "name": scenario.get("name"),
            "analysis_date": scenario.get("analysis_date"),
            "horizon_days": scenario.get("horizon_days"),
            "event": (
                {
                    "event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "duration_days": event.get("duration_days"),
                    "probability": event.get("probability"),
                    "probability_mode": event.get("probability_mode"),
                }
                if event else None
            ),
            "simulation_count": scenario.get("simulation_count"),
            "random_seed": scenario.get("random_seed"),
            "affected_entity_count": len(scenario.get("affected_entities", [])),
            "data_source_label": scenario.get("data_source_label", "simulated"),
        },
        "problem_definition": {
            "problem_id": problem["problem_id"],
            "source_phase": problem["source_phase"],
            "source_contract": problem["source_contract"],
            "horizon_days": problem["horizon"],
            "decision_variable_count": len(problem["decision_variables"]),
            "declared_constraint_count": len(problem["constraints"]),
            "matrix_row_count": run.get("matrix_row_count"),
            "total_demand_units": parameters.get("total_demand_units"),
            "auxiliary_variables": parameters.get("auxiliary_variables"),
            "procurement_bounds": parameters.get("procurement_bounds"),
            "eligible_offers": parameters.get("eligible_offers", []),
            "excluded_offers": parameters.get("excluded_offers", []),
            "event_point_parameters": parameters.get("event_point_parameters"),
        },
        "objective": {
            **objective,
            "demand_satisfaction_hard": parameters.get("demand_satisfaction_hard"),
            "shortage_penalty_per_unit": parameters.get("shortage_penalty_per_unit"),
            "budget": parameters.get("budget"),
            "min_fulfillment": parameters.get("min_fulfillment"),
        },
        "decision_variables": {
            "count": len(problem["decision_variables"]),
            "variables": [item for item in problem["decision_variables"]],
            "note": problem.get("parameters", {}).get("auxiliary_variables"),
        },
        "constraints": {
            "count": len(problem["constraints"]),
            "declared": [item for item in problem["constraints"]],
            "hard_soft_policy": (
                "demand_satisfaction is hard for minimize_total_cost and soft "
                "for the other objectives (shortage priced or maximized by the "
                "objective itself)."
            ),
        },
        "assumptions": list(problem.get("assumptions", [])),
        "solver_information": {
            "solver": result["solver"],
            "solver_version": result["solver_version"],
            "options": {
                "presolve": True,
                "mip_rel_gap": 0.0,
                "time_limit_seconds": run.get("config", {}).get(
                    "time_limit_seconds"
                ),
            },
            "backend_note": (
                "SciPy's milp ships the HiGHS branch-and-bound solver and is "
                "already a declared transitive dependency; no new dependency "
                "was installed. OR-Tools remains an uninstalled optional extra "
                "behind the same solver interface."
            ),
            "determinism": (
                "Fixed variable/row ordering, mip_rel_gap 0, scenario point "
                "parameters, no randomness; repeatability is enforced by the "
                "determinism tests."
            ),
        },
        "feasibility_status": feasibility,
        "objective_value": objective_value,
        "objective_breakdown": dict(result.get("objective_breakdown", {})),
        "decision_values": {
            "count": len(decision_values),
            "values": dict(decision_values),
            "units": "demand_units",
            "note": (
                "Order-quantity decisions with non-zero values only; auxiliary "
                "MOQ selectors are internal and excluded."
            ) if decision_values else (
                f"No decision values for status {status}."
            ),
        },
        "baseline_comparison": dict(result.get("baseline_comparison", {})),
        "scenario_comparison": dict(result.get("scenario_comparison", {})),
        "binding_constraints": binding,
        "slack_utilization": _utilization(result),
        "provenance": dict(problem.get("provenance", {})),
        "uncertainty": dict(run.get("uncertainty", {})),
        "warnings": warnings,
        "limitations": list(result.get("limitations", [])) + list(
            _FIXED_LIMITATIONS
        ),
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    """Render the 21-section report as Markdown."""
    lines = ["# Optimization Run Report (Synthetic / Simulated Data)", ""]
    for position, section in enumerate(REPORT_SECTIONS, start=1):
        title = SECTION_TITLES[section]
        lines.append(f"## {position}. {title}")
        lines.extend(_render_payload(report.get(section)))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_payload(payload: Any, depth: int = 0) -> list[str]:
    """Render one section payload as nested Markdown bullets."""
    indent = "  " * depth
    if payload is None:
        return [f"{indent}- Not available for this status."]
    if isinstance(payload, bool):
        return [f"{indent}- {payload}"]
    if isinstance(payload, (int, float)):
        return [f"{indent}- {payload}"]
    if isinstance(payload, str):
        return [f"{indent}- {payload}"]
    if isinstance(payload, dict):
        lines: list[str] = []
        for key, value in payload.items():
            if isinstance(value, (dict, list)) and value:
                lines.append(f"{indent}- **{key}**:")
                lines.extend(_render_payload(value, depth + 1))
            else:
                lines.append(f"{indent}- **{key}**: {_scalar(value)}")
        return lines or [f"{indent}- None."]
    if isinstance(payload, list):
        lines = []
        for item in payload:
            if isinstance(item, dict):
                first = next(iter(item.values()), "")
                lines.append(f"{indent}- {_scalar(first)}")
                lines.extend(_render_payload(item, depth + 1))
            else:
                lines.append(f"{indent}- {_scalar(item)}")
        return lines or [f"{indent}- None."]
    return [f"{indent}- {payload}"]


def _scalar(value: Any) -> str:
    """Format a scalar for Markdown output."""
    if value is None:
        return "Not available for this status."
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


__all__ = ["REPORT_SECTIONS", "SECTION_TITLES", "build_report", "render_markdown"]
