"""Baseline and scenario comparison (Phase 10).

- ``evaluate_plan`` re-runs the Phase 8 deterministic daily engine over the
  current plan plus extracted order decisions (report numbers).
- ``build_baseline_comparison`` contrasts the deterministic event-aware
  current plan with the same plan plus the optimized orders.
- ``build_scenario_comparison`` carries the Phase 9 factual baseline-vs-no-action
  deltas; the optimized plan is never re-simulated through Phase 9 (documented
  limitation, stated in the payload).

Baseline inputs are frozen dataclasses — nothing here mutates them.
All values are SYNTHETIC / simulated planning outputs.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from backend.app.analytics.optimization.inputs import (
    OptimizationInputs,
    SupplierOffer,
)
from backend.app.analytics.simulation import inventory_engine

_OUTCOME_METRICS = (
    "expected_unmet_demand",
    "stockout_probability",
    "expected_stockout_days",
    "expected_min_inventory",
    "expected_ending_inventory",
)


def evaluate_plan(
    inputs: OptimizationInputs, decision_values: dict[str, float],
) -> dict[str, Any]:
    """Evaluate current plan + orders with ``inventory_engine.run_days``."""
    offer_lookup: dict[tuple[str, str], SupplierOffer] = {
        (offer.supplier_id, offer.product_id): offer for offer in inputs.offers
    }
    served_total = 0.0
    unmet_total = 0.0
    demand_total = 0.0
    procurement_cost: float | None = 0.0
    by_entity: list[dict[str, Any]] = []
    for entity in inputs.entities:
        inbound = np.asarray(entity.existing_inbound, dtype=float).copy()
        for name, value in decision_values.items():
            if not name.startswith("order["):
                continue
            supplier_id, product_id, warehouse_id = (
                name[len("order["):-1].split("|")
            )
            if product_id != entity.product_id or warehouse_id != entity.warehouse_id:
                continue
            offer = offer_lookup.get((supplier_id, product_id))
            if offer is None or value <= 0:
                continue
            inbound[offer.arrival_day] += float(value) * offer.arrival_factor
            if offer.unit_cost is None:
                procurement_cost = None
            elif procurement_cost is not None:
                procurement_cost += offer.unit_cost * float(value)
        run = inventory_engine.run_days(
            entity.on_hand, np.asarray(entity.demand, dtype=float), inbound,
            np.asarray(entity.available, dtype=bool),
        )
        entity_demand = float(np.sum(entity.demand))
        entity_unmet = float(np.sum(run["unmet"]))
        entity_served = entity_demand - entity_unmet
        served_total += entity_served
        unmet_total += entity_unmet
        demand_total += entity_demand
        by_entity.append({
            "product_id": entity.product_id,
            "warehouse_id": entity.warehouse_id,
            "served_demand_units": round(entity_served, 6),
            "unmet_demand_units": round(entity_unmet, 6),
        })
    return {
        "served_demand_units": round(served_total, 6),
        "unmet_demand_units": round(unmet_total, 6),
        "fulfillment_rate": (
            round(served_total / demand_total, 6) if demand_total > 0 else None
        ),
        "procurement_cost": (
            None if procurement_cost is None else round(procurement_cost, 6)
        ),
        "by_entity": by_entity,
    }


def build_baseline_comparison(
    inputs: OptimizationInputs, decision_values: dict[str, float],
) -> dict[str, Any]:
    """Deterministic current plan vs current plan + optimized orders."""
    current_plan = {
        "served_demand_units": round(
            sum(entity.baseline_served for entity in inputs.entities), 6
        ),
        "unmet_demand_units": round(
            sum(entity.baseline_unmet for entity in inputs.entities), 6
        ),
        "fulfillment_rate": None,
        "procurement_cost": None,
        "note": (
            "Event-aware deterministic re-evaluation with point parameters "
            "(run_days); not the Phase 9 Monte Carlo baseline."
        ),
    }
    demand_total = float(sum(np.sum(entity.demand) for entity in inputs.entities))
    if demand_total > 0:
        current_plan["fulfillment_rate"] = round(
            float(current_plan["served_demand_units"]) / demand_total, 6
        )
    optimized = evaluate_plan(inputs, decision_values)
    deltas: dict[str, Any] = {
        "unmet_delta": round(
            optimized["unmet_demand_units"]
            - float(current_plan["unmet_demand_units"]), 6,
        ),
        "served_delta": round(
            optimized["served_demand_units"]
            - float(current_plan["served_demand_units"]), 6,
        ),
        "added_procurement_cost": optimized["procurement_cost"],
    }
    current_rate = current_plan["fulfillment_rate"]
    optimized_rate = optimized["fulfillment_rate"]
    deltas["fulfillment_rate_delta"] = (
        round(float(optimized_rate) - float(current_rate), 6)
        if current_rate is not None and optimized_rate is not None else None
    )
    return {
        "basis": "phase_10_deterministic_point_accounting",
        "current_plan": current_plan,
        "current_plan_plus_optimized_orders": optimized,
        "deltas": deltas,
        "note": (
            "Both sides use identical deterministic accounting: Phase 8 daily "
            "engine, scenario point parameters, same scope and horizon."
        ),
    }


def build_scenario_comparison(inputs: OptimizationInputs) -> dict[str, Any]:
    """Phase 9 factual baseline vs no-action arm (optimized not resimulated)."""
    if inputs.scenario_impact is None:
        return {
            "basis": "unavailable",
            "note": (
                "The replay run carries no NO_ACTION arm outcome; scenario "
                "comparison is unavailable for this run."
            ),
            "optimization_not_resimulated": True,
        }
    baseline_metrics = {
        key: inputs.baseline_outcome.get(key) for key in _OUTCOME_METRICS
    }
    no_action_metrics = {
        key: (inputs.no_action_outcome or {}).get(key)
        for key in _OUTCOME_METRICS
    }
    return {
        **inputs.scenario_impact,
        "phase9_baseline_outcome": baseline_metrics,
        "phase9_no_action_outcome": no_action_metrics,
        "optimization_not_resimulated": True,
        "limitation": (
            "The optimized plan is evaluated with deterministic point "
            "accounting only; it is not re-simulated through the Phase 9 "
            "Monte Carlo machinery, so it is not comparable line-by-line to "
            "the Phase 9 outcome metrics above."
        ),
    }
