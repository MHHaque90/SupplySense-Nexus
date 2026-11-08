"""Replay outcome wrappers (Phase 9).

Thin layer over Phase 8: aggregation mathematics is delegated to
``simulation.outcomes.aggregate`` and the typed ``ScenarioOutcome`` is
reused unchanged. Two small local helpers exist because the Phase 8
equivalents are private and must not be imported:

- ``summarize_run`` reduces one deterministic engine pass to scalars.
- ``account_effects`` mirrors supply-side accounting with the PUBLIC
  ``supply_effects`` functions.

Nothing here recomputes percentiles, probabilities, or any other
Phase 8 aggregation statistic.
"""

from datetime import date, timedelta
from typing import Any

import numpy as np

from backend.app.analytics.simulation import outcomes as simulation_outcomes
from backend.app.analytics.simulation import supply_effects
from backend.app.analytics.simulation.types import (
    ScenarioOutcome,
    SimulationConfig,
)


def summarize_run(run: dict[str, np.ndarray], horizon_days: int) -> dict[str, object]:
    """Reduce one engine pass to aggregation-ready scalars."""
    ending = np.asarray(run["ending"], dtype=float)
    unmet = np.asarray(run["unmet"], dtype=float)
    stockout = np.asarray(run["stockout_flag"], dtype=bool)
    hits = np.flatnonzero(stockout)
    first_day = int(hits[0]) if len(hits) else None
    return {
        "any_stockout": bool(stockout.any()),
        "stockout_days": float(stockout.sum()),
        "min_inventory": float(ending.min()) if horizon_days else 0.0,
        "ending_inventory": float(ending[-1]) if horizon_days else 0.0,
        "unmet_demand": float(unmet.sum()),
        "depleted": bool(ending[-1] <= 0) if horizon_days else False,
        "service_exposed": bool(unmet.sum() > 0),
        "stockout_by_7": bool(stockout[:7].any()) if horizon_days >= 7 else False,
        "stockout_by_14": bool(stockout[:14].any()) if horizon_days >= 14 else False,
        "stockout_by_28": bool(stockout[:28].any()) if horizon_days >= 28 else False,
        "first_stockout_date": None,
        "first_stockout_day": first_day,
    }


def calendar_dates(analysis_date: str, horizon_days: int) -> list[str]:
    """Return the horizon calendar used to date first stockouts."""
    origin = date.fromisoformat(analysis_date)
    return [
        (origin + timedelta(days=step)).isoformat()
        for step in range(1, horizon_days + 1)
    ]


def attach_dates(runs: list[dict[str, object]], calendar: list[str]) -> list[dict[str, object]]:
    """Attach the calendar date of the first stockout day to each run."""
    dated: list[dict[str, object]] = []
    for run in runs:
        item = dict(run)
        day = run.get("first_stockout_day")
        item["first_stockout_date"] = calendar[day] if isinstance(day, int) else None
        dated.append(item)
    return dated


def account_effects(
    schedule: list[dict[str, Any]],
    event: Any,
    params: dict[str, float],
    horizon_days: int,
) -> tuple[float, float, int]:
    """Supply-side accounting for one iteration of one arm.

    Returns (delayed_quantity, unavailable_quantity, affected_entries)
    using the same PUBLIC ``supply_effects`` calls as the Phase 8 engine.
    """
    arrivals = np.zeros(horizon_days)
    suppliers: list[str | None] = [None] * horizon_days
    for entry in schedule:
        offset = int(entry.get("day_offset", -1))
        if 0 <= offset < horizon_days:
            arrivals[offset] += float(entry["quantity"])
            suppliers[offset] = str(entry.get("supplier_id"))
    targets = list(event.affected_suppliers) if event else []
    duration = params.get("duration_days", event.duration_days if event else 0)
    duration = int(min(duration, horizon_days))
    delayed, unavailable, affected = 0.0, 0.0, 0
    parts = (
        list(event.components)
        if event and event.event_type == "COMBINED_DISRUPTION" and event.components
        else ([event] if event else [])
    )
    for part in parts:
        part_type = part.event_type
        part_targets = list(part.affected_suppliers) or targets
        if part_type in ("SUPPLIER_DISRUPTION", "COMBINED_DISRUPTION"):
            reduction = params.get("supply_reduction", part.supply_reduction)
            _, info = supply_effects.apply_supplier_disruption(
                arrivals, suppliers, part_targets, reduction, 0, duration)
            unavailable += info["unavailable_inbound_quantity"]
        if part_type == "SUPPLY_REDUCTION":
            reduction = params.get("supply_reduction", part.supply_reduction)
            _, info = supply_effects.apply_supply_reduction(
                arrivals, reduction, 0, duration)
            unavailable += info["unavailable_inbound_quantity"]
        if part_type in ("SHIPMENT_DELAY", "LEAD_TIME_DELAY", "COMBINED_DISRUPTION"):
            delay = int(params.get("lead_time_delay_days", part.lead_time_delay_days))
            _, info = supply_effects.apply_arrival_delay(arrivals, delay, 0, duration)
            delayed += info["delayed_inbound_quantity"]
    target_set = set(targets)
    for entry in schedule:
        offset = int(entry.get("day_offset", -1))
        if 0 <= offset < duration and str(entry.get("supplier_id")) in target_set:
            affected += 1
            break
    return delayed, unavailable, affected


def aggregate(
    runs: list[dict[str, object]],
    label: str,
    horizon_days: int,
    products: list[str],
    warehouses: list[str],
    suppliers: list[str],
    affected_pairs: int,
    inbound_count: int,
    delayed_quantity: float,
    unavailable_quantity: float,
    config: SimulationConfig,
) -> ScenarioOutcome:
    """Delegate aggregation to Phase 8 (no local aggregation math)."""
    return simulation_outcomes.aggregate(
        runs, label, horizon_days, products, warehouses, suppliers,
        affected_pairs, inbound_count, delayed_quantity, unavailable_quantity,
        config,
    )


def aggregate_baseline(
    runs: list[dict[str, object]],
    horizon_days: int,
    products: list[str],
    warehouses: list[str],
    suppliers: list[str],
    affected_pairs: int,
    config: SimulationConfig,
) -> ScenarioOutcome:
    """Aggregate the shared baseline (built once, never mutated by arms)."""
    return aggregate(
        runs, "baseline", horizon_days, products, warehouses, suppliers,
        affected_pairs, 0, 0.0, 0.0, config,
    )
