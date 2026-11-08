"""Stockout exposure analytics (Phase 5).

Categories are analytical statuses with documented thresholds, not
decisions: no_exposure (no current or projected stockout), watch
(projected stockout beyond the urgency window), elevated (projected
stockout inside the window), immediate (currently stocked out),
unknown (missing forecast or position).
"""

from backend.app.analytics.inventory.types import (
    ForecastInput,
    InventoryIntelligenceConfig,
    ProjectedInventoryPoint,
    StockoutExposure,
)


def assess_exposure(
    product_id: str,
    warehouse_id: str,
    on_hand: float | None,
    forecast: ForecastInput | None,
    trajectory: list[ProjectedInventoryPoint],
    config: InventoryIntelligenceConfig,
) -> StockoutExposure:
    """Assess stockout exposure from position and trajectory."""
    exposure = StockoutExposure(product_id=product_id, warehouse_id=warehouse_id)
    if on_hand is None or forecast is None or forecast.missing:
        exposure.exposure = "unknown"
        return exposure
    exposure.current_stockout = on_hand <= 0
    if exposure.current_stockout:
        exposure.exposure = "immediate"
        exposure.projected_stockout = True
        exposure.days_until_stockout = 0
        return exposure
    crossings = [point for point in trajectory if point.projected_stockout]
    if not crossings:
        exposure.exposure = "no_exposure"
        return exposure
    first = crossings[0]
    exposure.projected_stockout = True
    exposure.projected_stockout_date = first.date
    exposure.days_until_stockout = trajectory.index(first)
    exposure.horizon_stockout = True
    remaining = sum(
        point.forecast_demand for point in trajectory[trajectory.index(first):]
    )
    exposure.demand_remaining_at_stockout = remaining
    if exposure.days_until_stockout <= config.urgent_days:
        exposure.exposure = "elevated"
    else:
        exposure.exposure = "watch"
    return exposure
