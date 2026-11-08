"""Solver abstraction and SciPy/HiGHS MILP backend (Phase 10).

``OptimizationSolver`` is the stable interface; ``ScipyHiGHSSolver`` is the
only installed backend (SciPy ships HiGHS and is already a declared
transitive dependency of this project — no new dependency is introduced).
The roadmap's OR-Tools mention is honored behind this same interface if it is
ever installed (optional ``oracle`` extra); the deviation is documented in
``docs/optimization-engine.md``.

Determinism: presolve on, ``mip_rel_gap = 0``, fixed column/row ordering from
the formulation builder, and no randomness. Repeatability across consecutive
runs on identical inputs is enforced by the determinism test suite.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp

from backend.app.analytics.optimization.types import (
    OptimizationResult,
    ProblemFormulation,
)

_NAME_PREFIXES = ("order[", "unmet[", "served[")

_BUSINESS_ROW_TYPES = (
    "supplier_capacity",
    "minimum_order_quantity",
    "over_purchase_bound",
    "budget",
    "service_level_minimum",
    "demand_satisfaction",
)

_STATUS_BY_CODE = {
    0: "OPTIMAL",
    1: "FEASIBLE",
    2: "INFEASIBLE",
    3: "UNBOUNDED",
    4: "ERROR",
}

_TOL = 1e-6

_INF = float("inf")


class OptimizationSolver(Protocol):
    """Stable solver interface for the optimization engine."""

    name: str

    def solve(self, formulation: ProblemFormulation) -> OptimizationResult:
        """Solve one formulation and return a complete result object."""
        ...


def _collect_solution(
    formulation: ProblemFormulation, values: np.ndarray,
) -> tuple[dict[str, float], float, float]:
    """Extract order decisions plus served/unmet totals from the vector."""
    decision_values: dict[str, float] = {}
    served_total = 0.0
    unmet_total = 0.0
    for name, index in zip(formulation.variable_names, range(len(values))):
        value = float(values[index])
        if name.startswith("order["):
            if abs(value) > _TOL:
                decision_values[name] = round(value, 6)
        elif name.startswith("served["):
            served_total += value
        elif name.startswith("unmet["):
            unmet_total += value
    return dict(sorted(decision_values.items())), served_total, unmet_total


def _row_slacks(
    formulation: ProblemFormulation, values: np.ndarray,
) -> tuple[list[str], list[str], dict[str, float]]:
    """Compute binding, violated, and slack values for business rows."""
    products = formulation.constraint_matrix @ values
    binding: list[str] = []
    violated: list[str] = []
    slack: dict[str, float] = {}
    for position, row in enumerate(formulation.rows):
        if row.type not in _BUSINESS_ROW_TYPES:
            continue
        product = float(products[position])
        lower = row.lower
        upper = row.upper
        tolerance = _TOL * max(
            1.0, abs(lower) if lower is not None else 0.0,
            abs(upper) if upper is not None else 0.0,
        )
        slack_lower = _INF if lower is None else product - lower
        slack_upper = _INF if upper is None else upper - product
        row_slack = min(slack_lower, slack_upper)
        if slack_lower < -tolerance or slack_upper < -tolerance:
            violated.append(row.name)
        elif abs(row_slack) <= tolerance:
            binding.append(row.name)
        if np.isfinite(row_slack):
            slack[row.name] = round(float(row_slack), 6)
    return binding, violated, slack


class ScipyHiGHSSolver:
    """HiGHS branch-and-bound via ``scipy.optimize.milp``."""

    name = "scipy-milp-highs"

    def __init__(self, time_limit_seconds: float = 30.0) -> None:
        """Configure the backend; time limit bounds solver wall-clock use."""
        self.time_limit_seconds = float(time_limit_seconds)

    @property
    def version(self) -> str:
        """Return the solver identification string."""
        return f"scipy {scipy.__version__} (bundled HiGHS)"

    def solve(self, formulation: ProblemFormulation) -> OptimizationResult:
        """Solve one formulation; never raises — failures return ERROR."""
        problem = formulation.problem
        base: dict[str, Any] = {
            "problem_id": problem.problem_id,
            "scenario_id": problem.scenario_id,
            "solver": self.name,
            "solver_version": self.version,
            "baseline_comparison": {},
            "scenario_comparison": {},
            "assumptions": problem.assumptions,
            "provenance": problem.provenance.to_dict(),
            "analysis_date": problem.analysis_date,
            "problem": problem.to_dict(),
            "synthetic": True,
            "data_source_label": "simulated",
        }
        if not formulation.variable_names:
            return OptimizationResult(
                status="NO_DATA", feasible=False, objective_value=None,
                objective_breakdown={}, decision_values={},
                binding_constraints=(), violated_constraints=(), slack={},
                warnings=("No decision variables in scope; solver not called.",),
                limitations=("NO_DATA: nothing to optimize in the provided "
                             "scope.",),
                **base,
            )

        c_vector = formulation.objective_vector
        row_lower = np.full(len(formulation.rows), -_INF, dtype=float)
        row_upper = np.full(len(formulation.rows), _INF, dtype=float)
        for position, row in enumerate(formulation.rows):
            if row.lower is not None:
                row_lower[position] = row.lower
            if row.upper is not None:
                row_upper[position] = row.upper
        constraints = LinearConstraint(
            formulation.constraint_matrix, row_lower, row_upper,
        )
        bounds = Bounds(formulation.variable_lower, formulation.variable_upper)
        options: dict[str, Any] = {
            "disp": False,
            "presolve": True,
            "time_limit": self.time_limit_seconds,
            "mip_rel_gap": 0.0,
        }
        try:
            raw = milp(
                c=c_vector,
                constraints=constraints,
                integrality=formulation.integrality,
                bounds=bounds,
                options=options,
            )
        except Exception as exc:  # pragma: no cover - defensive backend guard
            return OptimizationResult(
                status="ERROR", feasible=False, objective_value=None,
                objective_breakdown={}, decision_values={},
                binding_constraints=(), violated_constraints=(), slack={},
                warnings=(f"Solver raised {type(exc).__name__}: {exc}",),
                limitations=("ERROR: the solver backend failed before "
                             "producing a solution.",),
                **base,
            )

        status = _STATUS_BY_CODE.get(int(raw.status), "ERROR")
        if status == "FEASIBLE" and raw.x is None:
            status = "ERROR"
        if status in ("INFEASIBLE", "UNBOUNDED", "ERROR") or raw.x is None:
            if status == "ERROR" and getattr(raw, "message", None):
                warning = f"Solver message: {raw.message}"
            else:
                warning = ""
            limitations = _status_limitations(status, formulation)
            warnings = (warning,) if warning else ()
            return OptimizationResult(
                status=status, feasible=False, objective_value=None,
                objective_breakdown={
                    "total_procurement_cost": None,
                    "total_unmet_demand": None,
                    "total_served_demand": None,
                    "fulfillment_rate": None,
                },
                decision_values={}, binding_constraints=(),
                violated_constraints=(), slack={},
                warnings=warnings, limitations=limitations, **base,
            )

        values = np.asarray(raw.x, dtype=float)
        decision_values, served_total, unmet_total = _collect_solution(
            formulation, values,
        )
        cost_total = 0.0
        for name, value in decision_values.items():
            if name in formulation.unit_costs:
                cost_total += formulation.unit_costs[name] * value
        objective_value = float(raw.fun)
        if problem.objective.direction == "maximize":
            objective_value = -objective_value
        penalty = problem.parameters.get("shortage_penalty_per_unit")
        breakdown: dict[str, float | None] = {
            "total_procurement_cost": round(cost_total, 6),
            "total_unmet_demand": round(unmet_total, 6),
            "total_served_demand": round(served_total, 6),
            "fulfillment_rate": (
                round(served_total / formulation.total_demand, 6)
                if formulation.total_demand > 0 else None
            ),
            "weighted_objective": round(objective_value, 6),
        }
        if penalty is not None:
            breakdown["shortage_penalty_cost"] = round(float(penalty) * unmet_total, 6)
        binding, violated, slack = _row_slacks(formulation, values)
        warnings: list[str] = []
        if violated:
            warnings.append(
                "Validation cross-check reported row violations: "
                + ", ".join(violated)
            )
        if status == "FEASIBLE":
            warnings.append(
                "Incumbent solution within the configured time limit; "
                "optimality was not certified."
            )
        return OptimizationResult(
            status=status,
            feasible=status in ("OPTIMAL", "FEASIBLE"),
            objective_value=round(objective_value, 6),
            objective_breakdown=breakdown,
            decision_values=decision_values,
            binding_constraints=tuple(binding),
            violated_constraints=tuple(violated),
            slack=dict(sorted(slack.items())),
            warnings=tuple(warnings),
            limitations=_status_limitations(status, formulation),
            **base,
        )


def _status_limitations(
    status: str, formulation: ProblemFormulation,
) -> tuple[str, ...]:
    """Honest, status-specific limitations for the report."""
    if status == "OPTIMAL":
        return (
            "Optimal only for the stated scalar objective and constraints under "
            "the configured horizon and scenario point parameters; feasibility "
            "of any downstream execution is not asserted here.",
        )
    if status == "FEASIBLE":
        return (
            "Feasible incumbent found within the time limit; a better solution "
            "may exist (optimality gap not closed).",
        )
    if status == "INFEASIBLE":
        return (
            "Structural diagnostics only; a minimal conflict (IIS) set is not "
            "available from this solver backend.",
        )
    if status == "UNBOUNDED":
        return ("Unbounded ray detected; check declared bounds and objective.",)
    return ("ERROR: no solution vector was produced.",)


__all__ = ["OptimizationSolver", "ScipyHiGHSSolver"]
