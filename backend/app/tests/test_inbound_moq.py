"""Phase 6 inbound coverage and MOQ tests."""

import pandas as pd

from backend.app.analytics.inventory.types import ForecastInput
from backend.app.analytics.procurement import inbound, moq
from backend.app.analytics.procurement.types import OpenOrderMetrics


def _forecast(point):
    total = len(point)
    return ForecastInput(
        product_id="P1", warehouse_id="W1", origin="2026-06-30",
        forecast_dates=[f"2026-07-{day:02d}" for day in range(1, total + 1)],
        horizon=total, point=list(point),
        lower=list(point), upper=list(point),
    )


def _order(product="P1", expected="2026-07-05", remaining=40.0):
    return OpenOrderMetrics(
        po_id="PO1", po_number="PO-001", supplier_id="S1", product_id=product,
        order_date="2026-06-01", expected_arrival=expected,
        ordered_quantity=remaining, received_quantity=0.0,
        remaining_quantity=remaining, arrival_status="expected",
    )


def test_supported_inbound():
    result = inbound.describe_inbound_coverage(
        "P1", "W1", _forecast([10.0] * 5), 100.0, [], "2026-07-05"
    )
    assert result.state == "INBOUND_SUPPORTED"
    assert result.known_inbound == 0.0
    assert result.uncovered_demand == 0.0


def test_partial_inbound():
    result = inbound.describe_inbound_coverage(
        "P1", "W1", _forecast([10.0] * 5), 20.0, [_order(remaining=15.0)], "2026-07-05"
    )
    assert result.state == "INBOUND_INSUFFICIENT"
    assert result.known_inbound == 15.0
    assert result.uncovered_demand == 15.0


def test_insufficient_vs_no_known_inbound():
    result = inbound.describe_inbound_coverage(
        "P1", "W1", _forecast([10.0] * 5), 20.0, [], "2026-07-05"
    )
    assert result.state == "NO_KNOWN_INBOUND"
    assert result.uncovered_demand == 30.0
    result = inbound.describe_inbound_coverage(
        "P1", "W1", _forecast([10.0] * 5), 20.0,
        [_order(expected="2026-08-01", remaining=100.0)], "2026-07-05"
    )
    assert result.state == "NO_KNOWN_INBOUND"  # arrival outside window


def test_unknown_inbound():
    result = inbound.describe_inbound_coverage("P1", "W1", None, 20.0, [], "2026-07-05")
    assert result.state == "UNKNOWN"
    assert inbound.partial_inbound_flag([]) is False


def test_moq_compliance_and_ratios():
    lines = pd.DataFrame({
        "supplier_id": ["S1"] * 4,
        "product_id": ["P1"] * 4,
        "quantity": [10.0, 25.0, 50.0, 100.0],
    })
    result = moq.describe_moq("S1", "P1", lines, 25.0)
    assert result.orders == 4
    assert result.compliant_orders == 3
    assert result.compliance_rate == 0.75
    assert result.below_moq_orders == 1
    assert result.min_order_ratio == 0.4
    assert result.median_order_ratio == 1.5


def test_moq_missing_terms():
    lines = pd.DataFrame({"supplier_id": ["S1"], "product_id": ["P1"], "quantity": [5.0]})
    result = moq.describe_moq("S1", "P1", lines, None)
    assert result.compliance_rate is None
    assert result.orders == 0
    result = moq.describe_moq("S1", "P1", lines.iloc[0:0], 10.0)
    assert result.orders == 0
    assert result.compliance_rate is None
