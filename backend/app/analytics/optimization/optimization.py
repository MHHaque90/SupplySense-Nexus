"""Optimization orchestration (Phase 10).

``run_optimization`` wires the layers together:

1. build inputs from public Phase 9 outputs (documented contract),
2. construct the MILP formulation for the declared objective,
3. solve through the abstracted solver backend,
4. independently validate the solution (bounds, rows, run_days cross-check),
5. assemble baseline and scenario comparisons,
6. return a complete, JSON-serializable run payload consumed by
   ``reports.build_report``.

Deterministic: no randomness, fixed ordering, wall-clock timings excluded
from payload comparisons by the determinism tests. All outputs are
SYNTHETIC / simulated planning data.
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

import pandas as pd

from backend.app.analytics.inventory.types import ForecastInput
from backend.app.analytics.optimization import (
    comparison as comparison_mod,
)
from backend.app.analytics.optimization import (
    inputs as inputs_mod,
)
from backend.app.analytics.optimization import (
    problem as problem_mod,
)
from backend.app.analytics.optimization import (
    validation as validation_mod,
)
from backend.app.analytics.optimization.solver import (
    OptimizationSolver,
    ScipyHiGHSSolver,
)
from backend.app.analytics.optimization.types import (
    OptimizationConfig,
)

_UNAVAILABLE_COMPARISON = {
    "status": "unavailable",
    "note": (
        "No feasible solution vector exists for this status; baseline "
        "comparison is unavailable."
    ),
}


def _structural_diagnostics(
    inputs: inputs_mod.OptimizationInputs,
    eligible: tuple[inputs_mod.SupplierOffer, ...],
    config: OptimizationConfig,
) -> list[str]:
    """Structural causes for INFEASIBLE status (honest, no IIS claim)."""
    diagnostics: list[str] = []
    products = sorted({entity.product_id for entity in inputs.entities})
    for product_id in products:
        offers = [offer for offer in eligible if offer.product_id == product_id]
        if not offers:
            diagnostics.append(
                f"No eligible supplier offers for product {product_id} "
                "in the scoped horizon."
            )
            continue
        capacity_known = [offer.capacity_units for offer in offers]
        if all(value is not None for value in capacity_known):
            total_capacity = float(sum(value or 0.0 for value in capacity_known))
            demand = float(sum(
                sum(entity.demand) for entity in inputs.entities
                if entity.product_id == product_id
            ))
            if total_capacity < demand:
                diagnostics.append(
                    f"Product {product_id}: summed supplier capacity "
                    f"{total_capacity:.6f} is below in-scope demand "
                    f"{demand:.6f}."
                )
        demand = float(sum(
            sum(entity.demand) for entity in inputs.entities
            if entity.product_id == product_id
        ))
        on_hand = float(sum(
            entity.on_hand for entity in inputs.entities
            if entity.product_id == product_id
        ))
        inbound = float(sum(
            sum(entity.existing_inbound) for entity in inputs.entities
            if entity.product_id == product_id
        ))
        if demand > on_hand + inbound + 1e-9 and config.budget is None:
            diagnostics.append(
                f"Product {product_id}: on-hand plus existing inbound "
                f"({on_hand + inbound:.6f}) covers less than in-scope demand "
                f"({demand:.6f}); hard demand satisfaction needs new orders."
            )
        if config.budget is not None:
            known_costs = [
                offer.unit_cost for offer in offers if offer.unit_cost is not None
            ]
            if known_costs:
                cheapest = min(known_costs)
                if cheapest * demand > float(config.budget):
                    diagnostics.append(
                        f"Product {product_id}: cheapest observed unit cost "
                        f"({cheapest}) times in-scope demand "
                        f"({demand:.6f}) exceeds the configured budget "
                        f"({config.budget})."
                    )
    lead_exclusions = [
        item for item in inputs.excluded_offers
        if item["reason"] in (
            "lead_time_outside_horizon", "lead_time_nonpositive",
            "arrival_eliminated_by_scenario", "lead_time_missing",
        )
    ]
    if lead_exclusions:
        diagnostics.append(
            f"{len(lead_exclusions)} supplier-product link(s) excluded by the "
            "lead-time horizon rule (reasons recorded in problem parameters)."
        )
    if config.min_fulfillment is not None and inputs.entities:
        demand = float(sum(sum(entity.demand) for entity in inputs.entities))
        served = float(sum(entity.baseline_served for entity in inputs.entities))
        if demand > 0 and served / demand > float(config.min_fulfillment):
            diagnostics.append(
                "Configured minimum fulfillment is above the deterministic "
                "current-plan rate; check hard demand satisfaction and "
                "capacity rows."
            )
    if not diagnostics:
        diagnostics.append(
            "No structural cause identified by the available diagnostics; the "
            "conflict involves interacting rows (full conflict set unavailable "
            "from this backend)."
        )
    return diagnostics


def run_optimization(
    replay_run: dict[str, Any],
    entities: list[dict[str, Any]],
    supplier_links: pd.DataFrame,
    config: OptimizationConfig | None = None,
    forecast_by_series: dict[str, ForecastInput] | None = None,
    product_id: str | None = None,
    warehouse_id: str | None = None,
    supplier_id: str | None = None,
    solver: OptimizationSolver | None = None,
) -> dict[str, Any]:
    """Run one complete optimization over public Phase 9 outputs.

    Raises ``ValueError`` for malformed replay runs, malformed entities,
    missing supplier-link columns, or invalid configuration.
    """
    started = time.perf_counter()
    config = config or OptimizationConfig()
    inputs = inputs_mod.build_optimization_inputs(
        replay_run, entities, supplier_links, config=config,
        forecast_by_series=forecast_by_series, product_id=product_id,
        warehouse_id=warehouse_id, supplier_id=supplier_id,
    )
    inputs_done = time.perf_counter()

    formulation = problem_mod.build_formulation(inputs, config)
    constructed_done = time.perf_counter()

    active_solver = solver or ScipyHiGHSSolver(
        time_limit_seconds=config.time_limit_seconds,
    )
    result = active_solver.solve(formulation)
    solved_done = time.perf_counter()

    checks, validation_warnings = validation_mod.validate_result(
        result, formulation, inputs,
    )
    validated_done = time.perf_counter()

    eligible, _, cost_warnings = problem_mod.eligible_offers_for(inputs, config)
    if result.feasible:
        baseline_comparison = comparison_mod.build_baseline_comparison(
            inputs, result.decision_values,
        )
    else:
        baseline_comparison = dict(_UNAVAILABLE_COMPARISON)
    scenario_comparison = comparison_mod.build_scenario_comparison(inputs)

    diagnostics: list[str] = []
    if result.status == "INFEASIBLE":
        diagnostics = _structural_diagnostics(inputs, eligible, config)

    merged_warnings = list(result.warnings)
    for item in inputs.warnings:
        if item not in merged_warnings:
            merged_warnings.append(item)
    for item in cost_warnings:
        if item not in merged_warnings:
            merged_warnings.append(item)
    for item in validation_warnings:
        if item not in merged_warnings:
            merged_warnings.append(item)
    if result.status == "NO_DATA":
        merged_warnings.append(
            "NO_DATA: the scoped inputs produced no decision variables "
            "(empty entity scope or no eligible supplier offers)."
        )

    result = replace(
        result,
        baseline_comparison=baseline_comparison,
        scenario_comparison=scenario_comparison,
        warnings=tuple(merged_warnings),
    )

    total_done = time.perf_counter()
    run: dict[str, Any] = {
        "optimization_id": result.problem_id,
        "replay_id": inputs.provenance.replay_id,
        "scenario_id": inputs.scenario["scenario_id"],
        "scenario": inputs.scenario,
        "config": config.to_dict(),
        "problem": formulation.problem.to_dict(),
        "result": result.to_dict(),
        "checks": [check.to_dict() for check in checks],
        "diagnostics": diagnostics,
        "input_warnings": list(inputs.warnings),
        "validation_warnings": validation_warnings,
        "matrix_row_count": len(formulation.rows),
        "uncertainty": dict(inputs.uncertainty),
        "timings": {
            "input_preparation": round(inputs_done - started, 6),
            "problem_construction": round(constructed_done - inputs_done, 6),
            "solver": round(solved_done - constructed_done, 6),
            "result_validation": round(validated_done - solved_done, 6),
            "total": round(total_done - started, 6),
        },
        "synthetic": True,
        "data_source_label": "simulated",
    }
    return run


__all__ = ["run_optimization"]
