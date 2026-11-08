"""Baseline state generation (Phase 8).

The baseline is built ONCE per scenario from current inventory,
Phase 4 forecasts (point/lower/upper, never retrained), known inbound,
open POs, and observed lead-time context. It represents the same
starting state for both baseline and disrupted runs and is never
affected by disruption assumptions.
"""

from datetime import date, timedelta
from typing import Any

from backend.app.analytics.inventory import projection as projection_mod


def forecast_dates(origin: date, horizon_days: int) -> list[str]:
    """Return ISO forecast dates starting the day after origin."""
    return [
        (origin + timedelta(days=step)).isoformat()
        for step in range(1, horizon_days + 1)
    ]


def build_baseline_series(
    product_id: str,
    warehouse_id: str,
    on_hand: float,
    forecast_point: list[float],
    forecast_lower: list[float],
    forecast_upper: list[float],
    origin: date,
    horizon_days: int,
    shipments,
    po_lines,
    analysis_date: date,
    forecast_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one baseline series state (pure function of observed inputs)."""
    horizon_end = analysis_date + timedelta(days=horizon_days)
    inbound = projection_mod.known_inbound(
        product_id, shipments, po_lines, analysis_date, horizon_end
    )
    meta = dict(forecast_meta or {})
    return {
        "product_id": product_id,
        "warehouse_id": warehouse_id,
        "on_hand": float(on_hand),
        "demand_point": [float(value) for value in forecast_point[:horizon_days]],
        "demand_lower": [float(value) for value in forecast_lower[:horizon_days]],
        "demand_upper": [float(value) for value in forecast_upper[:horizon_days]],
        "origin": origin.isoformat(),
        "forecast_dates": forecast_dates(origin, horizon_days),
        "horizon_days": horizon_days,
        "inbound": {day: float(quantity) for day, quantity in inbound.items()},
        "forecast_meta": meta,
    }
