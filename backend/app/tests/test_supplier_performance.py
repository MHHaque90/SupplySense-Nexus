"""Phase 6 supplier performance tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.procurement import supplier_performance
from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG

ANALYSIS = date(2026, 6, 30)
CONFIG = DEFAULT_PROCUREMENT_CONFIG


def _lines():
    return pd.DataFrame({
        "po_id": ["PO1", "PO1", "PO2"],
        "supplier_id": ["S1", "S1", "S1"],
        "product_id": ["P1", "P2", "P1"],
        "order_date": [date(2026, 1, 5), date(2026, 1, 5), date(2026, 2, 1)],
        "quantity": [100.0, 50.0, 200.0],
        "status": ["received", "received", "ordered"],
    })


def _shipments():
    return pd.DataFrame({
        "shipment_id": ["SH1", "SH2"],
        "po_id": ["PO1", "PO2"],
        "supplier_id": ["S1", "S1"],
        "expected_arrival_date": [date(2026, 1, 15), date(2026, 2, 10)],
        "actual_arrival_date": [date(2026, 1, 15), date(2026, 2, 13)],
        "delay_days": [0.0, 3.0],
    })


def test_po_aggregation():
    result = supplier_performance.describe_supplier(
        "S1", "Supplier One", _lines(), _shipments(), ANALYSIS, CONFIG
    )
    assert result.po_count == 2
    assert result.po_line_count == 3
    assert result.ordered_quantity == 350.0
    assert result.shipment_count == 2


def test_received_quantity_inference_documented():
    result = supplier_performance.describe_supplier(
        "S1", "Supplier One", _lines(), _shipments(), ANALYSIS, CONFIG
    )
    # Both POs have delivered shipments, so all lines count as received.
    assert result.received_quantity == 350.0


def test_on_time_and_delay_calculation():
    result = supplier_performance.describe_supplier(
        "S1", "Supplier One", _lines(), _shipments(), ANALYSIS, CONFIG
    )
    assert result.completed_shipments == 2
    assert result.on_time_shipments == 1
    assert result.late_shipments == 1
    assert result.on_time_rate == 0.5
    assert result.average_delay_days == 1.5
    assert result.median_delay_days == 1.5
    assert result.max_delay_days == 3.0


def test_lead_time_calculation():
    result = supplier_performance.describe_supplier(
        "S1", "Supplier One", _lines(), _shipments(), ANALYSIS, CONFIG
    )
    assert result.average_lead_time_days == (10 + 12) / 2
    assert result.min_lead_time_days == 10.0
    assert result.max_lead_time_days == 12.0


def test_missing_evidence_explicit():
    result = supplier_performance.describe_supplier(
        "SX", "Nobody", _lines(), _shipments(), ANALYSIS, CONFIG
    )
    assert result.po_count == 0
    assert result.received_quantity is None
    assert "purchase_order_history" in result.missing_evidence
    assert "delivered_shipments" in result.missing_evidence
    assert result.on_time_rate is None


def test_future_records_excluded():
    future_lines = _lines().copy()
    future_lines.loc[len(future_lines)] = ["PO9", "S1", "P1", date(2026, 12, 1), 999.0, "ordered"]
    future_shipments = _shipments().copy()
    future_shipments.loc[len(future_shipments)] = [
        "SH9", "PO9", "S1", date(2026, 12, 10), date(2026, 12, 20), 10.0
    ]
    result = supplier_performance.describe_supplier(
        "S1", "Supplier One", future_lines, future_shipments, ANALYSIS, CONFIG
    )
    assert result.po_count == 2
    assert result.completed_shipments == 2
    assert result.ordered_quantity == 350.0
