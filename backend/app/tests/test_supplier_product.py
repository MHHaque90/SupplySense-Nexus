"""Phase 6 supplier-product relationship tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.inventory.types import InventoryHealth
from backend.app.analytics.procurement import supplier_product
from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG

ANALYSIS = date(2026, 6, 30)
CONFIG = DEFAULT_PROCUREMENT_CONFIG


def _lines():
    return pd.DataFrame({
        "po_id": ["PO1", "PO2"],
        "supplier_id": ["S1", "S1"],
        "product_id": ["P1", "P1"],
        "order_date": [date(2026, 1, 5), date(2026, 2, 1)],
        "quantity": [100.0, 50.0],
        "status": ["received", "ordered"],
    })


def _shipments():
    return pd.DataFrame({
        "shipment_id": ["SH1"],
        "po_id": ["PO1"],
        "supplier_id": ["S1"],
        "expected_arrival_date": [date(2026, 1, 15)],
        "actual_arrival_date": [date(2026, 1, 16)],
        "delay_days": [1.0],
    })


def _intelligence(health="AT_RISK", warehouse="W1"):
    return [InventoryIntelligenceResult(
        product_id="P1", warehouse_id=warehouse, analysis_date="2026-06-30",
        health=InventoryHealth(product_id="P1", warehouse_id=warehouse,
                               health=health, reason="test"),
    )]


def test_relationship_aggregation():
    result = supplier_product.describe_relationship(
        "S1", "Supplier One", "P1", "Widget", _lines(), _shipments(),
        25.0, ANALYSIS, CONFIG, _intelligence(),
    )
    assert result.po_count == 2
    assert result.ordered_quantity == 150.0
    assert result.received_quantity == 100.0
    assert result.shipment_count == 1
    assert result.on_time_rate == 0.0  # 1-day delay beyond grace 0
    assert result.moq == 25.0
    assert result.moq_compliance_rate == 1.0


def test_warehouse_exposure_preserved():
    result = supplier_product.describe_relationship(
        "S1", "Supplier One", "P1", "Widget", _lines(), _shipments(),
        25.0, ANALYSIS, CONFIG,
        _intelligence("AT_RISK", "W1") + _intelligence("HEALTHY", "W2"),
    )
    assert result.exposed_warehouses == ["W1", "W2"]
    assert result.at_risk_warehouses == ["W1"]
    assert result.stockout_warehouses == []


def test_stockout_warehouses_tracked():
    result = supplier_product.describe_relationship(
        "S1", "Supplier One", "P1", "Widget", _lines(), _shipments(),
        25.0, ANALYSIS, CONFIG, _intelligence("STOCKOUT", "W9"),
    )
    assert result.stockout_warehouses == ["W9"]


def test_missing_supplier_history():
    result = supplier_product.describe_relationship(
        "SX", "Nobody", "P1", "Widget", _lines(), _shipments(),
        None, ANALYSIS, CONFIG, [],
    )
    assert result.po_count == 0
    assert result.ordered_quantity == 0.0
    assert result.received_quantity is None
    assert result.moq_compliance_rate is None
    assert result.exposed_warehouses == []
