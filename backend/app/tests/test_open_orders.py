"""Phase 6 open purchase order tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.procurement import open_orders

ANALYSIS = date(2026, 6, 30)


def _lines():
    return pd.DataFrame({
        "po_id": ["PO1", "PO2", "PO3"],
        "po_number": ["PO-001", "PO-002", "PO-003"],
        "supplier_id": ["S1", "S1", "S1"],
        "product_id": ["P1", "P1", "P1"],
        "order_date": [date(2026, 6, 1), date(2026, 6, 10), date(2026, 5, 1)],
        "expected_delivery_date": [date(2026, 7, 5), date(2026, 6, 20), date(2026, 6, 10)],
        "quantity": [100.0, 50.0, 30.0],
        "status": ["ordered", "partially_received", "received"],
    })


def _shipments():
    return pd.DataFrame({
        "shipment_id": ["SH1", "SH2"],
        "po_id": ["PO2", "PO3"],
        "expected_arrival_date": [date(2026, 6, 20), date(2026, 6, 10)],
        "actual_arrival_date": [date(2026, 6, 21), date(2026, 6, 10)],
    })


def test_remaining_quantity():
    results = {order.po_id: order for order in open_orders.describe_open_orders(
        _lines(), _shipments(), ANALYSIS
    )}
    assert set(results) == {"PO1", "PO2"}  # received PO3 excluded
    assert results["PO1"].remaining_quantity == 100.0
    assert results["PO1"].received_quantity == 0.0
    assert results["PO2"].remaining_quantity == 0.0  # delivered shipment covers line
    assert results["PO2"].received_quantity == 50.0


def test_overdue_inbound():
    empty_shipments = pd.DataFrame({
        "shipment_id": [], "po_id": [],
        "expected_arrival_date": [], "actual_arrival_date": [],
    })
    results = {order.po_id: order for order in open_orders.describe_open_orders(
        _lines(), empty_shipments, ANALYSIS
    )}
    assert results["PO2"].overdue is True
    assert results["PO2"].arrival_status == "overdue"
    assert results["PO1"].overdue is False
    assert results["PO1"].arrival_status == "expected"
    assert results["PO1"].days_outstanding == 29


def test_expected_inbound_not_overdue():
    results = open_orders.describe_open_orders(_lines(), _shipments(), ANALYSIS)
    by_id = {order.po_id: order for order in results}
    assert by_id["PO1"].expected_arrival == "2026-07-05"


def test_empty_open_order_state():
    assert open_orders.describe_open_orders(
        _lines().iloc[0:0], _shipments(), ANALYSIS
    ) == []
    received_only = _lines()[_lines()["po_id"] == "PO3"]
    assert open_orders.describe_open_orders(received_only, _shipments(), ANALYSIS) == []
