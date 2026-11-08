"""Typed Optimization Engine contracts (Phase 10).

Frozen dataclasses with JSON-serializable ``to_dict`` views, mirroring the
Phase 9 replay contract style. Every field that carries data lineage is
explicit; nothing here is invented at runtime.

All values produced by this module are SYNTHETIC / simulated planning outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

OBJECTIVES = (
    "minimize_total_cost",
    "minimize_shortage",
    "cost_shortage_tradeoff",
    "maximize_service_fulfillment",
)

STATUSES = (
    "OPTIMAL",
    "FEASIBLE",
    "INFEASIBLE",
    "UNBOUNDED",
    "ERROR",
    "NO_DATA",
)

CONSTRAINT_TYPES = (
    "demand_satisfaction",
    "daily_balance",
    "supplier_capacity",
    "minimum_order_quantity",
    "over_purchase_bound",
    "lead_time_horizon",
    "budget",
    "service_level_minimum",
)

HardOrSoft = Literal["hard", "soft"]


@dataclass(frozen=True)
class OptimizationConfig:
    """Explicit optimization configuration. Every setting is documented.

    - objective: one of ``OBJECTIVES``; no silent multi-objective weighting.
    - shortage_penalty_per_unit: required (> 0) for ``cost_shortage_tradeoff``.
    - budget: optional hard procurement budget; ``None`` disables the row.
    - min_fulfillment: optional hard lower bound on fulfillment rate in [0, 1].
    - quantity_integrality: ``"integer"`` orders (default) or ``"continuous"``.
    - time_limit_seconds: solver wall-clock limit for the MILP.
    """

    objective: str = "minimize_total_cost"
    shortage_penalty_per_unit: float | None = None
    budget: float | None = None
    min_fulfillment: float | None = None
    quantity_integrality: str = "integer"
    time_limit_seconds: float = 30.0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the configuration."""
        return {
            "objective": self.objective,
            "shortage_penalty_per_unit": self.shortage_penalty_per_unit,
            "budget": self.budget,
            "min_fulfillment": self.min_fulfillment,
            "quantity_integrality": self.quantity_integrality,
            "time_limit_seconds": self.time_limit_seconds,
        }


DEFAULT_OPTIMIZATION_CONFIG = OptimizationConfig()


@dataclass(frozen=True)
class DecisionVariable:
    """One exposed decision variable (an order quantity a planner controls).

    Auxiliary solver internals (MOQ binary selectors) are recorded in the
    problem ``parameters`` instead of being exposed here.
    """

    name: str
    entity_type: str
    entity_id: str
    supplier_id: str
    product_id: str
    warehouse_id: str
    lower_bound: float
    upper_bound: float | None
    integrality: str
    units: str
    source: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the variable."""
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "supplier_id": self.supplier_id,
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "integrality": self.integrality,
            "units": self.units,
            "source": self.source,
            "description": self.description,
        }


@dataclass(frozen=True)
class Constraint:
    """One declared constraint (structural rows included for auditability)."""

    name: str
    type: str
    expression: str
    bound: float | None
    units: str
    hard_or_soft: HardOrSoft
    source: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the constraint."""
        return {
            "name": self.name,
            "type": self.type,
            "expression": self.expression,
            "bound": self.bound,
            "units": self.units,
            "hard_or_soft": self.hard_or_soft,
            "source": self.source,
            "description": self.description,
        }


@dataclass(frozen=True)
class ObjectiveComponent:
    """One weighted component of the scalar objective."""

    name: str
    weight: float
    units: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the component."""
        return {"name": self.name, "weight": self.weight, "units": self.units}


@dataclass(frozen=True)
class Objective:
    """The declared scalar objective: direction, components, weights, units."""

    name: str
    direction: str
    components: tuple[ObjectiveComponent, ...]
    units: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the objective."""
        return {
            "name": self.name,
            "direction": self.direction,
            "components": [item.to_dict() for item in self.components],
            "units": self.units,
            "description": self.description,
        }


@dataclass(frozen=True)
class Provenance:
    """Lineage of an optimization run back to Phase 9 and forecast models."""

    source_phase: str
    source_module: str
    replay_id: str
    scenario_id: str
    scenario_fingerprint: str
    baseline_ref: str
    sample_fingerprint: str
    analysis_date: str
    forecast_references: tuple[dict[str, Any], ...]
    product_ids: tuple[str, ...]
    warehouse_ids: tuple[str, ...]
    supplier_ids: tuple[str, ...]
    synthetic: bool = True
    data_source_label: str = "simulated"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the provenance."""
        return {
            "source_phase": self.source_phase,
            "source_module": self.source_module,
            "replay_id": self.replay_id,
            "scenario_id": self.scenario_id,
            "scenario_fingerprint": self.scenario_fingerprint,
            "baseline_ref": self.baseline_ref,
            "sample_fingerprint": self.sample_fingerprint,
            "analysis_date": self.analysis_date,
            "forecast_references": [dict(item) for item in self.forecast_references],
            "product_ids": list(self.product_ids),
            "warehouse_ids": list(self.warehouse_ids),
            "supplier_ids": list(self.supplier_ids),
            "synthetic": self.synthetic,
            "data_source_label": self.data_source_label,
        }


@dataclass(frozen=True)
class OptimizationProblem:
    """A fully declared, JSON-serializable optimization problem definition."""

    problem_id: str
    scenario_id: str
    analysis_date: str
    horizon: int
    objective: Objective
    decision_variables: tuple[DecisionVariable, ...]
    constraints: tuple[Constraint, ...]
    parameters: dict[str, Any]
    assumptions: tuple[str, ...]
    provenance: Provenance
    source_phase: str
    source_contract: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the problem definition."""
        return {
            "problem_id": self.problem_id,
            "scenario_id": self.scenario_id,
            "analysis_date": self.analysis_date,
            "horizon": self.horizon,
            "objective": self.objective.to_dict(),
            "decision_variables": [item.to_dict() for item in self.decision_variables],
            "constraints": [item.to_dict() for item in self.constraints],
            "parameters": dict(self.parameters),
            "assumptions": list(self.assumptions),
            "provenance": self.provenance.to_dict(),
            "source_phase": self.source_phase,
            "source_contract": self.source_contract,
        }


@dataclass(frozen=True)
class ConstraintRow:
    """One matrix row of the MILP formulation (solver-facing, named)."""

    name: str
    type: str
    lower: float | None
    upper: float | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the row."""
        return {"name": self.name, "type": self.type, "lower": self.lower, "upper": self.upper}


@dataclass(frozen=True)
class ProblemFormulation:
    """Solver-facing MILP formulation bound to its problem definition.

    Matrices use the SciPy ``milp`` conventions: minimize ``c @ x`` subject to
    ``lower <= A @ x <= upper`` and per-column bounds/integrality
    (0 = continuous, 1 = integer).
    """

    problem: OptimizationProblem
    variable_names: tuple[str, ...]
    objective_vector: np.ndarray
    variable_lower: np.ndarray
    variable_upper: np.ndarray
    integrality: np.ndarray
    constraint_matrix: np.ndarray
    rows: tuple[ConstraintRow, ...]
    unit_costs: dict[str, float] = field(default_factory=dict)
    total_demand: float = 0.0
    horizon: int = 0


@dataclass(frozen=True)
class OptimizationResult:
    """The outcome of one optimization run.

    - status: exactly one of ``STATUSES``.
    - feasible: True only for ``OPTIMAL``/``FEASIBLE``.
    - decision_values: exposed order-quantity decisions (solver solution).
    - binding/violated constraints: named rows; violated is empty unless the
      validation cross-check found a problem.
    - slack: named row slack/utilization values from the solved formulation.
    - baseline/scenario comparisons: computed by the comparison layer.
    """

    problem_id: str
    scenario_id: str
    status: str
    feasible: bool
    solver: str
    solver_version: str
    objective_value: float | None
    objective_breakdown: dict[str, float | None]
    decision_values: dict[str, float]
    binding_constraints: tuple[str, ...]
    violated_constraints: tuple[str, ...]
    slack: dict[str, float]
    baseline_comparison: dict[str, Any]
    scenario_comparison: dict[str, Any]
    assumptions: tuple[str, ...]
    provenance: dict[str, Any]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    analysis_date: str
    problem: dict[str, Any]
    synthetic: bool = True
    data_source_label: str = "simulated"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the result."""
        return {
            "problem_id": self.problem_id,
            "scenario_id": self.scenario_id,
            "status": self.status,
            "feasible": self.feasible,
            "solver": self.solver,
            "solver_version": self.solver_version,
            "objective_value": self.objective_value,
            "objective_breakdown": dict(self.objective_breakdown),
            "decision_values": dict(self.decision_values),
            "binding_constraints": list(self.binding_constraints),
            "violated_constraints": list(self.violated_constraints),
            "slack": dict(self.slack),
            "baseline_comparison": dict(self.baseline_comparison),
            "scenario_comparison": dict(self.scenario_comparison),
            "assumptions": list(self.assumptions),
            "provenance": dict(self.provenance),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "analysis_date": self.analysis_date,
            "problem": dict(self.problem),
            "synthetic": self.synthetic,
            "data_source_label": self.data_source_label,
        }
