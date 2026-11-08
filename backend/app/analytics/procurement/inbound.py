"""Inbound coverage states for inventory series (Phase 6).

Compares known inbound (from open-order expected arrivals inside the
window) against uncovered horizon demand. States are descriptive;
arrival is never certain when information is missing.
"""

from backend.app.analytics.inventory.types import ForecastInput
from backend.app.analytics.procurement.types import InboundCoverage, OpenOrderMetrics


def describe_inbound_coverage(
    product_id: str,
    warehouse_id: str,
    forecast: ForecastInput | None,
    on_hand: float | None,
    open_orders: list[OpenOrderMetrics],
    horizon_end: str,
) -> InboundCoverage:
    """Classify inbound coverage for one series."""
    result = InboundCoverage(product_id=product_id, warehouse_id=warehouse_id)
    if forecast is None or forecast.missing or on_hand is None:
        result.reason = "Unknown without forecast and inventory position."
        return result
    horizon_demand = sum(forecast.point)
    shortfall = max(0.0, horizon_demand - on_hand)
    inbound = sum(
        order.remaining_quantity for order in open_orders
        if order.product_id == product_id
        and order.expected_arrival is not None
        and order.expected_arrival <= horizon_end
        and order.remaining_quantity > 0
    )
    result.known_inbound = inbound
    if shortfall <= 0:
        result.state = "INBOUND_SUPPORTED"
        result.uncovered_demand = 0.0
        result.reason = "On-hand covers horizon demand without inbound."
    elif inbound <= 0:
        result.state = "NO_KNOWN_INBOUND"
        result.uncovered_demand = shortfall
        result.reason = "No expected arrivals inside the horizon window."
    elif inbound >= shortfall:
        result.state = "INBOUND_SUPPORTED"
        result.uncovered_demand = 0.0
        result.reason = "Known inbound covers the demand shortfall."
    else:
        result.state = "INBOUND_INSUFFICIENT"
        result.uncovered_demand = shortfall - inbound
        result.reason = "Known inbound covers only part of the demand shortfall."
    return result


def partial_inbound_flag(open_orders: list[OpenOrderMetrics]) -> bool:
    """Return True when any open order is only partially received."""
    return any(
        0.0 < order.received_quantity < order.ordered_quantity for order in open_orders
    )
