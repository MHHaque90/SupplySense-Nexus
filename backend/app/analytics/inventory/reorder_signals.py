"""Reorder-point SIGNALS (Phase 5, descriptive only).

The threshold is expected demand over a configured coverage period
plus an INFORMATIONAL uncertainty buffer taken directly from the mean
forecast interval width. This is not an optimized safety stock, not a
service-level optimum, and not a cost optimum. Output is a threshold,
current inventory, signal status, and reason — never an order quantity,
supplier, or timing decision.
"""

from backend.app.analytics.inventory.types import (
    ForecastInput,
    InventoryIntelligenceConfig,
    ReorderSignal,
    StockoutExposure,
)


def reorder_threshold(
    forecast: ForecastInput | None,
    config: InventoryIntelligenceConfig,
) -> tuple[float | None, float | None]:
    """Compute (threshold, uncertainty_buffer) from forecast demand.

    Returns (None, None) when the forecast is missing or the coverage
    window has no expected demand.
    """
    if forecast is None or forecast.missing or not forecast.point:
        return None, None
    window = forecast.point[: max(1, config.coverage_period_days)]
    expected = sum(window) / len(window) * config.coverage_period_days
    widths = [hi - lo for hi, lo in zip(forecast.upper, forecast.lower)]
    buffer = (sum(widths) / len(widths) * config.uncertainty_buffer_factor) if widths else 0.0
    return expected + buffer, buffer


def reorder_signal(
    product_id: str,
    warehouse_id: str,
    on_hand: float | None,
    forecast: ForecastInput | None,
    stockout: StockoutExposure | None,
    days_of_supply: float | None,
    config: InventoryIntelligenceConfig,
) -> ReorderSignal:
    """Evaluate the reorder threshold crossing and urgency category."""
    signal = ReorderSignal(product_id=product_id, warehouse_id=warehouse_id,
                           current_inventory=on_hand)
    if on_hand is None or forecast is None or forecast.missing:
        signal.urgency = "unknown"
        signal.reason = "Reorder threshold cannot be evaluated without inventory and forecast."
        return signal
    threshold, buffer = reorder_threshold(forecast, config)
    signal.threshold = threshold
    signal.uncertainty_buffer = buffer
    if threshold is None:
        signal.urgency = "unknown"
        signal.reason = "No expected demand in the coverage window."
        return signal
    signal.below_threshold = on_hand < threshold
    if not signal.below_threshold:
        signal.urgency = "no_signal"
        signal.reason = (
            f"On-hand {on_hand:.0f} is above the reorder threshold {threshold:.0f}."
        )
        return signal
    days = stockout.days_until_stockout if stockout else None
    if days is not None and days <= config.urgent_days:
        signal.urgency = "urgent"
        signal.reason = (
            f"Below threshold {threshold:.0f} with projected stockout in {days} days. "
            "Analytical signal only; no order quantity is computed."
        )
    elif days is not None and days <= config.plan_days:
        signal.urgency = "plan"
        signal.reason = (
            f"Below threshold {threshold:.0f}; projected stockout in {days} days."
        )
    elif days_of_supply is not None and days_of_supply <= config.critical_dos:
        signal.urgency = "urgent"
        signal.reason = (
            f"Below threshold {threshold:.0f} with {days_of_supply:.1f} days of supply."
        )
    else:
        signal.urgency = "monitor"
        signal.reason = (
            f"Below threshold {threshold:.0f}; monitor coverage over the horizon."
        )
    return signal
