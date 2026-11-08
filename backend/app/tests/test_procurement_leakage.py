"""Phase 6 point-in-time leakage tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.procurement import (
    delivery,
    open_orders,
    service_impact,
    supplier_performance,
)
from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG

ANALYSIS = date(2026, 6, 30)
CONFIG = DEFAULT_PROCUREMENT_CONFIG


def _lines(extra_future=True):
    rows = [
        ["PO1", "S1", "P1", date(2026, 1, 5), date(2026, 1, 20), 100.0, "ordered"],
        ["PO2", "S1", "P1", date(2026, 2, 1), date(2026, 2, 15), 50.0, "ordered"],
    ]
    if extra_future:
        rows.append(["PO9", "S1", "P1", date(2026, 12, 1), date(2026, 12, 20), 9999.0, "ordered"])
    return pd.DataFrame(rows, columns=[
        "po_id", "supplier_id", "product_id", "order_date", "expected_delivery_date",
        "quantity", "status",
    ])


def _shipments(extra_future=True):
    rows = [
        ["SH1", "PO1", "S1", date(2026, 1, 10), date(2026, 1, 15), date(2026, 1, 16), 1.0],
        ["SH2", "PO2", "S1", date(2026, 2, 5), date(2026, 2, 12), date(2026, 2, 12), 0.0],
    ]
    if extra_future:
        rows.append(["SH9", "PO9", "S1", date(2026, 12, 5), date(2026, 12, 20),
                     date(2027, 1, 15), 26.0])
    return pd.DataFrame(rows, columns=[
        "shipment_id", "po_id", "supplier_id", "shipped_date",
        "expected_arrival_date", "actual_arrival_date", "delay_days",
    ])


def test_future_po_excluded():
    clean = supplier_performance.describe_supplier(
        "S1", "S", _lines(False), _shipments(False), ANALYSIS, CONFIG
    )
    dirty = supplier_performance.describe_supplier(
        "S1", "S", _lines(True), _shipments(True), ANALYSIS, CONFIG
    )
    assert dirty.to_dict() == clean.to_dict()


def test_future_shipment_excluded_from_delivery():
    clean = delivery.describe_delivery("S1", _shipments(False), ANALYSIS, CONFIG)
    dirty = delivery.describe_delivery("S1", _shipments(True), ANALYSIS, CONFIG)
    assert dirty.to_dict() == clean.to_dict()


def test_future_shipment_event_window():
    from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
    from backend.app.analytics.inventory.types import InventoryHealth

    intelligence = [InventoryIntelligenceResult(
        product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
        health=InventoryHealth(product_id="P1", warehouse_id="W1",
                               health="AT_RISK", reason="test"),
    )]
    early = service_impact.describe_cooccurrence(
        "S1", _shipments(False), intelligence, ANALYSIS, recent_window_days=90
    )
    assert early == [] or all(item.delayed_shipments <= 2 for item in early)
    # Future delayed arrival must not enter the recent window.
    future_only = _shipments(True)[_shipments(True)["shipment_id"] == "SH9"]
    result = service_impact.describe_cooccurrence(
        "S1", future_only, intelligence, ANALYSIS, recent_window_days=90
    )
    assert result == []


def test_open_orders_ignore_future_pos():
    clean = open_orders.describe_open_orders(_lines(False), _shipments(False), ANALYSIS)
    dirty = open_orders.describe_open_orders(_lines(True), _shipments(True), ANALYSIS)
    assert [order.to_dict() for order in dirty] == [order.to_dict() for order in clean]
