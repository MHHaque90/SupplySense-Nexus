"""Scenario simulation orchestrator (Phase 8).

Builds the baseline ONCE per scenario, then runs the disrupted
scenario deterministically (count == 1) or as Monte Carlo over
explicitly configured distributions. Forecasts are consumed, never
retrained; Phase 4 intervals are never recalculated.
"""

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.app.analytics.simulation import (
    demand_effects,
    inventory_engine,
    supply_effects,
)


def build_inbound_schedule(
    product_id: str,
    shipments: pd.DataFrame,
    po_lines: pd.DataFrame,
    analysis_date: date,
    horizon_end: date,
    forecast_dates: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Build attributed inbound arrivals for one product.

    One contribution per open PO/product at its earliest expected
    arrival inside the window (same documented rule as Phase 5
    inbound mapping, plus supplier attribution for targeting).
    Undelivered means actual arrival is null. Each entry carries its
    horizon day_offset when forecast_dates are provided.
    """
    schedule: list[dict[str, Any]] = []
    if shipments.empty or po_lines.empty:
        return schedule
    pending = shipments[
        (shipments["actual_arrival_date"].isna())
        & (pd.to_datetime(shipments["expected_arrival_date"]).dt.date > analysis_date)
        & (pd.to_datetime(shipments["expected_arrival_date"]).dt.date <= horizon_end)
    ]
    lines = po_lines[po_lines["product_id"] == product_id]
    if pending.empty or lines.empty:
        return schedule
    line_qty = lines.groupby("po_id")["quantity"].sum().astype(float)
    line_supplier = lines.drop_duplicates("po_id").set_index("po_id")["supplier_id"].astype(str)
    earliest: dict[str, dict[str, Any]] = {}
    for _, row in pending.iterrows():
        po_id = str(row["po_id"])
        if po_id not in line_qty.index:
            continue
        arrival = str(pd.to_datetime(row["expected_arrival_date"]).date())
        if po_id not in earliest or arrival < earliest[po_id]["date"]:
            earliest[po_id] = {
                "date": arrival,
                "quantity": float(line_qty.loc[po_id]),
                "supplier_id": str(line_supplier.loc[po_id]),
                "po_id": po_id,
            }
    for entry in earliest.values():
        offset = forecast_dates.index(entry["date"]) if forecast_dates and entry["date"] in forecast_dates else -1
        schedule.append({
            "date": entry["date"],
            "day_offset": offset,
            "quantity": entry["quantity"],
            "supplier_id": entry["supplier_id"],
            "po_id": entry["po_id"],
            "affected_by_event": False,
            "event_id": None,
        })
    return sorted(schedule, key=lambda item: item["date"])


def _window(event, horizon_days: int) -> tuple[int, int]:
    duration = min(event.duration_days, horizon_days) if event else 0
    return 0, duration


def run_entity_once(
    on_hand: float,
    demand_point: list[float],
    schedule: list[dict[str, Any]],
    horizon_days: int,
    event,
    params: dict[str, float],
) -> dict[str, np.ndarray]:
    """Run one deterministic pass for one entity."""
    demand = np.asarray(demand_point[:horizon_days], dtype=float)
    arrivals = np.zeros(horizon_days)
    suppliers: list[str | None] = [None] * horizon_days
    for entry in schedule:
        offset = int(entry.get("day_offset", -1))
        if 0 <= offset < horizon_days:
            arrivals[offset] += float(entry["quantity"])
            suppliers[offset] = str(entry.get("supplier_id")) or suppliers[offset]
    start, duration = _window(event, horizon_days)
    affected_by = event.affected_suppliers if event else []
    mask = np.ones(horizon_days, dtype=bool)
    parts = (
        list(event.components)
        if event and event.event_type == "COMBINED_DISRUPTION" and event.components
        else ([event] if event else [])
    )
    for part in parts:
        part_type = part.event_type
        window_end = start + duration if duration else horizon_days
        part_targets = list(part.affected_suppliers) or affected_by
        if part_type == "DEMAND_SHOCK":
            demand, _, _ = demand_effects.apply_demand_multiplier(
                demand, demand, demand,
                params.get("demand_multiplier", part.demand_multiplier),
                start, window_end,
            )
        if part_type in ("SUPPLIER_DISRUPTION", "COMBINED_DISRUPTION"):
            arrivals, _ = supply_effects.apply_supplier_disruption(
                arrivals, suppliers, part_targets,
                params.get("supply_reduction", part.supply_reduction), start, duration,
            )
        if part_type == "SUPPLY_REDUCTION":
            arrivals, _ = supply_effects.apply_supply_reduction(
                arrivals, params.get("supply_reduction", part.supply_reduction),
                start, duration,
            )
        if part_type in ("SHIPMENT_DELAY", "LEAD_TIME_DELAY", "COMBINED_DISRUPTION"):
            delay = int(params.get("lead_time_delay_days", part.lead_time_delay_days))
            arrivals, _ = supply_effects.apply_arrival_delay(
                arrivals, delay, start, duration,
            )
        if part_type == "WAREHOUSE_DISRUPTION":
            mask[start:window_end] = False
    return inventory_engine.run_days(on_hand, demand, arrivals, mask)


def run_baseline_once(
    on_hand: float,
    demand_point: list[float],
    schedule: list[dict[str, Any]],
    horizon_days: int,
) -> dict[str, np.ndarray]:
    """Run the undisrupted baseline once (no event effects)."""
    demand = np.asarray(demand_point[:horizon_days], dtype=float)
    arrivals = np.zeros(horizon_days)
    for entry in schedule:
        offset = int(entry.get("day_offset", -1))
        if 0 <= offset < horizon_days:
            arrivals[offset] += float(entry["quantity"])
    return inventory_engine.run_days(on_hand, demand, arrivals, None)
