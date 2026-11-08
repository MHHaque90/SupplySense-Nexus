"""Independent result validation (Phase 10).

Re-derives every check from the extracted solution and the Phase 8 daily
engine — it never trusts the solver's own accounting:

- decision bounds and integrality,
- full row feasibility of the solved formulation,
- a ``run_days`` cross-check of served/unmet totals for the extracted order
  plan (greedy serve-early totals equal the LP-optimal totals for fixed
  arrivals),
- objective arithmetic consistency from the reported breakdown,
- scope consistency (formulation total demand still matches the inputs),
- provenance completeness and synthetic labeling.

Checks return explicit ``PASS`` / ``FAIL`` / ``UNCHECKED`` notes, mirroring
the Phase 9 validation convention. FAIL notes are surfaced as warnings; they
never disappear silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from backend.app.analytics.optimization.inputs import (
    OptimizationInputs,
    SupplierOffer,
)
from backend.app.analytics.optimization.types import (
    OptimizationConfig,
    OptimizationResult,
    ProblemFormulation,
)
from backend.app.analytics.simulation import inventory_engine

_TOL = 1e-4


@dataclass(frozen=True)
class ValidationCheck:
    """One named validation check with an explicit status."""

    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the check."""
        return {"name": self.name, "status": self.status, "detail": self.detail}

    @property
    def note(self) -> str:
        """Render the check as a report note."""
        return f"{self.status}: {self.name} — {self.detail}"


def _order_key(name: str) -> tuple[str, str, str]:
    """Parse ``order[supplier|product|warehouse]`` into its components."""
    return tuple(name[len("order["):-1].split("|"))  # type: ignore[return-value]


def _orders_by_entity(
    decision_values: dict[str, float],
) -> dict[tuple[str, str], list[tuple[str, str, float]]]:
    """Group ordered quantities by (product, warehouse) with supplier ids."""
    grouped: dict[tuple[str, str], list[tuple[str, str, float]]] = {}
    for name, value in decision_values.items():
        if not name.startswith("order["):
            continue
        supplier_id, product_id, warehouse_id = _order_key(name)
        grouped.setdefault((product_id, warehouse_id), []).append(
            (supplier_id, product_id, float(value))
        )
    return grouped


def _check_bounds_integrality(
    formulation: ProblemFormulation, values: dict[str, float], integer_orders: bool,
) -> list[ValidationCheck]:
    """Bounds and (when configured) integrality of order decisions."""
    checks: list[ValidationCheck] = []
    index = {name: position for position, name in enumerate(formulation.variable_names)}
    bound_failures: list[str] = []
    integer_failures: list[str] = []
    for name, value in values.items():
        position = index[name]
        lower = formulation.variable_lower[position]
        upper = formulation.variable_upper[position]
        if value < lower - _TOL or value > upper + _TOL:
            bound_failures.append(name)
        if integer_orders and abs(value - round(value)) > _TOL:
            integer_failures.append(name)
    checks.append(ValidationCheck(
        name="decision_bounds",
        status="FAIL" if bound_failures else "PASS",
        detail=(
            f"{len(bound_failures)} decision(s) outside bounds."
            if bound_failures else "All order decisions inside declared bounds."
        ),
    ))
    checks.append(ValidationCheck(
        name="decision_integrality",
        status="FAIL" if integer_failures else ("PASS" if integer_orders else "UNCHECKED"),
        detail=(
            f"{len(integer_failures)} non-integral decision(s)."
            if integer_failures else
            ("All order decisions integral (integer mode)." if integer_orders
             else "Continuous mode: integrality not required.")
        ),
    ))
    return checks


def _reconstructed_vector(
    formulation: ProblemFormulation,
    inputs: OptimizationInputs,
    values: dict[str, float],
) -> np.ndarray:
    """Full formulation vector: extracted orders + deterministic state.

    Served/unmet/balance columns are re-derived with
    ``inventory_engine.run_days`` (greedy serve-early pattern satisfies the
    daily rows by construction), so definitional rows can be checked
    independently of the solver's internal state vector. Business rows are
    checked by the solver on the true solution (``violated_constraints``).
    """
    index = {name: position for position, name in enumerate(formulation.variable_names)}
    vector = np.zeros(len(formulation.variable_names), dtype=float)
    for name, value in values.items():
        vector[index[name]] = value
    offer_lookup: dict[tuple[str, str], SupplierOffer] = {
        (offer.supplier_id, offer.product_id): offer for offer in inputs.offers
    }
    ordered_by_link: dict[tuple[str, str], float] = {}
    for name, value in values.items():
        if name.startswith("order[") and value > 0:
            supplier_id, product_id, _ = _order_key(name)
            key = (supplier_id, product_id)
            ordered_by_link[key] = ordered_by_link.get(key, 0.0) + float(value)
    for offer in inputs.offers:
        binary_name = f"moq_used[{offer.supplier_id}|{offer.product_id}]"
        if binary_name in index:
            vector[index[binary_name]] = (
                1.0 if ordered_by_link.get(
                    (offer.supplier_id, offer.product_id), 0.0
                ) > 0 else 0.0
            )
    for entity in inputs.entities:
        inbound = np.asarray(entity.existing_inbound, dtype=float).copy()
        for name, value in values.items():
            if not name.startswith("order["):
                continue
            supplier_id, product_id, warehouse_id = _order_key(name)
            if product_id != entity.product_id or warehouse_id != entity.warehouse_id:
                continue
            offer = offer_lookup.get((supplier_id, product_id))
            if offer is None or value <= 0:
                continue
            inbound[offer.arrival_day] += float(value) * offer.arrival_factor
        run = inventory_engine.run_days(
            entity.on_hand, np.asarray(entity.demand, dtype=float), inbound,
            np.asarray(entity.available, dtype=bool),
        )
        prefix = f"{entity.product_id}|{entity.warehouse_id}"
        vector[index[f"balance[{prefix}]:day00"]] = entity.on_hand
        for day in range(formulation.horizon):
            vector[index[f"balance[{prefix}]:day{day + 1:02d}"]] = float(
                run["ending"][day]
            )
            unmet = float(run["unmet"][day])
            vector[index[f"unmet[{prefix}]:day{day:02d}"]] = unmet
            vector[index[f"served[{prefix}]:day{day:02d}"]] = (
                float(entity.demand[day]) - unmet
            )
    return vector


def _check_rows(
    formulation: ProblemFormulation,
    inputs: OptimizationInputs,
    values: dict[str, float],
) -> ValidationCheck:
    """Recompute every formulation row from the reconstructed vector."""
    vector = _reconstructed_vector(formulation, inputs, values)
    products = formulation.constraint_matrix @ vector
    violations: list[str] = []
    for position, row in enumerate(formulation.rows):
        product = float(products[position])
        if row.lower is not None and product < row.lower - _TOL:
            violations.append(row.name)
        elif row.upper is not None and product > row.upper + _TOL:
            violations.append(row.name)
    return ValidationCheck(
        name="row_feasibility",
        status="FAIL" if violations else "PASS",
        detail=(
            f"{len(violations)} row(s) violated: {', '.join(violations[:5])}."
            if violations else
            "All formulation rows satisfied within tolerance for the "
            "extracted orders plus deterministic state re-derivation."
        ),
    )


def _check_inventory_cross(
    formulation: ProblemFormulation,
    inputs: OptimizationInputs,
    values: dict[str, float],
    breakdown: dict[str, float | None],
) -> ValidationCheck:
    """Re-evaluate the extracted plan with ``inventory_engine.run_days``."""
    offer_lookup: dict[tuple[str, str], SupplierOffer] = {
        (offer.supplier_id, offer.product_id): offer for offer in inputs.offers
    }
    grouped = _orders_by_entity(values)
    served_total = 0.0
    unmet_total = 0.0
    for entity in inputs.entities:
        key = (entity.product_id, entity.warehouse_id)
        inbound = np.asarray(entity.existing_inbound, dtype=float)
        for supplier_id, product_id, quantity in grouped.get(key, []):
            offer = offer_lookup.get((supplier_id, product_id))
            if offer is None or quantity <= 0:
                continue
            inbound = inbound.copy()
            inbound[offer.arrival_day] += quantity * offer.arrival_factor
        run = inventory_engine.run_days(
            entity.on_hand, np.asarray(entity.demand, dtype=float), inbound,
            np.asarray(entity.available, dtype=bool),
        )
        unmet = float(np.sum(run["unmet"]))
        unmet_total += unmet
        served_total += float(np.sum(entity.demand)) - unmet
    reported_unmet = breakdown.get("total_unmet_demand")
    reported_served = breakdown.get("total_served_demand")
    if reported_unmet is None or reported_served is None:
        return ValidationCheck(
            name="inventory_cross_check", status="UNCHECKED",
            detail="No solution totals reported for this status.",
        )
    matches = (
        abs(reported_unmet - unmet_total) <= _TOL
        and abs(reported_served - served_total) <= _TOL
    )
    return ValidationCheck(
        name="inventory_cross_check",
        status="PASS" if matches else "FAIL",
        detail=(
            "run_days re-evaluation of the extracted plan matches reported "
            "served/unmet totals."
            if matches else
            f"run_days totals (served={served_total:.6f}, unmet={unmet_total:.6f}) "
            f"differ from reported (served={reported_served}, unmet={reported_unmet})."
        ),
    )


def _check_objective_arithmetic(
    problem: dict[str, Any],
    objective_value: float | None,
    breakdown: dict[str, float | None],
) -> ValidationCheck:
    """Recompute the weighted objective from its declared components."""
    if objective_value is None:
        return ValidationCheck(
            name="objective_arithmetic", status="UNCHECKED",
            detail="No objective value reported for this status.",
        )
    config = OptimizationConfig(
        objective=str(problem["parameters"]["objective_key"]),
        shortage_penalty_per_unit=problem["parameters"].get(
            "shortage_penalty_per_unit"
        ),
    )
    cost = breakdown.get("total_procurement_cost")
    unmet = breakdown.get("total_unmet_demand")
    served = breakdown.get("total_served_demand")
    expected: float | None = None
    if config.objective == "minimize_total_cost" and cost is not None:
        expected = cost
    elif config.objective == "minimize_shortage" and unmet is not None:
        expected = unmet
    elif config.objective == "cost_shortage_tradeoff" and cost is not None and unmet is not None:
        penalty = float(config.shortage_penalty_per_unit or 0.0)
        expected = cost + penalty * unmet
    elif config.objective == "maximize_service_fulfillment" and served is not None:
        expected = served
    if expected is None:
        return ValidationCheck(
            name="objective_arithmetic", status="UNCHECKED",
            detail="Objective components unavailable for recomputation.",
        )
    matches = abs(expected - objective_value) <= max(_TOL, abs(expected) * 1e-6)
    return ValidationCheck(
        name="objective_arithmetic",
        status="PASS" if matches else "FAIL",
        detail=(
            f"Declared objective recomputes to {expected:.6f} "
            f"(reported {objective_value:.6f})."
            if matches else
            f"Objective mismatch: recomputed {expected:.6f} vs reported "
            f"{objective_value:.6f}."
        ),
    )


def _check_scope_consistency(
    formulation: ProblemFormulation, inputs: OptimizationInputs,
) -> ValidationCheck:
    """Formulation total demand must still match the input entities."""
    total = float(sum(np.sum(entity.demand) for entity in inputs.entities))
    matches = abs(total - formulation.total_demand) <= _TOL
    return ValidationCheck(
        name="scope_consistency",
        status="PASS" if matches else "FAIL",
        detail=(
            f"Formulation total demand {formulation.total_demand:.6f} matches "
            f"inputs ({total:.6f})."
            if matches else
            f"Formulation total demand {formulation.total_demand:.6f} differs "
            f"from inputs ({total:.6f}); inputs mutated after formulation."
        ),
    )


def _check_provenance(
    formulation: ProblemFormulation, result: OptimizationResult,
) -> ValidationCheck:
    """Provenance and synthetic labeling must be present and honest."""
    problem = formulation.problem
    provenance = problem.provenance
    complete = bool(
        provenance.replay_id
        and provenance.scenario_id
        and provenance.source_phase == "phase_9_decision_replay"
        and provenance.synthetic
        and provenance.data_source_label == "simulated"
        and result.synthetic
        and result.data_source_label == "simulated"
        and result.provenance.get("scenario_fingerprint")
    )
    return ValidationCheck(
        name="provenance_completeness",
        status="PASS" if complete else "FAIL",
        detail=(
            "Provenance carries replay/scenario lineage and simulated labeling."
            if complete else "Provenance or synthetic labeling is incomplete."
        ),
    )


def validate_result(
    result: OptimizationResult,
    formulation: ProblemFormulation,
    inputs: OptimizationInputs,
) -> tuple[tuple[ValidationCheck, ...], tuple[str, ...]]:
    """Run every independent check; returns (checks, warnings)."""
    integer_orders = (
        formulation.problem.parameters.get("quantity_integrality") == "integer"
    )
    checks: list[ValidationCheck] = []
    checks.append(_check_scope_consistency(formulation, inputs))
    checks.append(_check_provenance(formulation, result))
    checks.append(_check_objective_arithmetic(
        result.problem, result.objective_value, result.objective_breakdown,
    ))
    if not result.decision_values:
        checks.append(ValidationCheck(
            name="row_feasibility", status="UNCHECKED",
            detail="No decision values for this status.",
        ))
        checks.append(ValidationCheck(
            name="inventory_cross_check", status="UNCHECKED",
            detail="No decision values for this status.",
        ))
        checks.append(ValidationCheck(
            name="decision_bounds", status="UNCHECKED",
            detail="No decision values for this status.",
        ))
        checks.append(ValidationCheck(
            name="decision_integrality", status="UNCHECKED",
            detail="No decision values for this status.",
        ))
    else:
        checks.extend(_check_bounds_integrality(
            formulation, result.decision_values, integer_orders,
        ))
        checks.append(_check_rows(formulation, inputs, result.decision_values))
        checks.append(_check_inventory_cross(
            formulation, inputs, result.decision_values,
            result.objective_breakdown,
        ))
    warnings = tuple(
        check.note for check in checks if check.status == "FAIL"
    )
    return tuple(checks), warnings
