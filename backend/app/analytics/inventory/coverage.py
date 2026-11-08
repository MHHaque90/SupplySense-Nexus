"""Demand coverage and days-of-supply analytics (Phase 5).

Two labeled perspectives that are never silently substituted:
- forecast-based (from the selected Phase 4 forecast), and
- historical (from observed demand averages).

Zero expected demand yields an explicit ``unbounded`` state; missing
forecasts yield ``unknown``. No division-by-zero values are produced.
"""

from backend.app.analytics.inventory.types import CoverageResult, ForecastInput


def forecast_coverage(
    product_id: str,
    warehouse_id: str,
    on_hand: float | None,
    forecast: ForecastInput | None,
    historical_daily_demand: float | None = None,
) -> CoverageResult:
    """Compute coverage ratios and days of supply for one series."""
    result = CoverageResult(product_id=product_id, warehouse_id=warehouse_id)
    if historical_daily_demand is not None and historical_daily_demand > 0 and on_hand is not None:
        result.historical_days_of_supply = on_hand / historical_daily_demand
    if forecast is None or forecast.missing or on_hand is None:
        return result
    point_total = sum(forecast.point)
    lower_total = sum(forecast.lower)
    upper_total = sum(forecast.upper)
    result.horizon_demand_point = point_total
    result.horizon_demand_lower = lower_total
    result.horizon_demand_upper = upper_total
    days = max(1, forecast.horizon)
    daily = point_total / days
    if daily <= 0:
        # Zero expected demand with stock on hand: unbounded coverage.
        result.forecast_days_of_supply_state = "unbounded" if on_hand > 0 else "unknown"
        result.forecast_days_of_supply = None
    else:
        result.forecast_days_of_supply = on_hand / daily
        result.forecast_days_of_supply_state = "finite"
    # Coverage ratio labels name the demand case explicitly: higher
    # forecast demand means lower coverage.
    if point_total > 0:
        result.coverage_ratio_point = on_hand / point_total
    if lower_total > 0:
        result.coverage_ratio_lower_demand = on_hand / lower_total
    if upper_total > 0:
        result.coverage_ratio_upper_demand = on_hand / upper_total
    return result
