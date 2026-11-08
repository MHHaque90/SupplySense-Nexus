"""Phase 6 supplier-linked inventory exposure tests."""

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.inventory.types import ForecastInput, InventoryHealth, ReorderSignal
from backend.app.analytics.procurement import exposure
from backend.app.analytics.procurement.types import OpenOrderMetrics


def _result(product, warehouse, health, urgency="no_signal", limited=False):
    forecast = None
    if limited:
        forecast = ForecastInput(
            product_id=product, warehouse_id=warehouse, origin="2026-06-30",
            confidence={"level": "limited validation support"},
        )
    return InventoryIntelligenceResult(
        product_id=product, warehouse_id=warehouse, analysis_date="2026-06-30",
        forecast=forecast,
        health=InventoryHealth(product_id=product, warehouse_id=warehouse,
                               health=health, reason="test"),
        reorder=ReorderSignal(product_id=product, warehouse_id=warehouse, urgency=urgency),
    )


def _order(supplier="S1", remaining=40.0):
    return OpenOrderMetrics(
        po_id="PO1", po_number="PO-001", supplier_id=supplier, product_id="P1",
        order_date="2026-06-01", remaining_quantity=remaining,
    )


def test_exposure_counts_and_traceability():
    intelligence = [
        _result("P1", "W1", "AT_RISK", "urgent", limited=True),
        _result("P1", "W2", "STOCKOUT"),
        _result("P2", "W1", "HEALTHY"),
        _result("P9", "W1", "CRITICAL"),
    ]
    result = exposure.describe_supplier_exposure(
        "S1", "Supplier One", ["P1", "P2"], intelligence, [_order()], {("PO1", "P1"): 25.0}
    )
    assert result.affected_products == ["P1", "P2"]
    assert result.affected_warehouses == ["W1", "W2"]
    assert result.at_risk_products == ["P1"]
    assert result.stockout_products == ["P1"]
    assert result.urgent_products == ["P1"]
    assert result.high_uncertainty_products == ["P1"]
    assert result.open_po_quantity == 40.0
    assert result.inbound_quantity == 25.0
    assert "P9" not in result.affected_products


def test_exposure_without_intelligence():
    result = exposure.describe_supplier_exposure(
        "S1", "Supplier One", ["P1"], [], [_order()], None
    )
    assert result.affected_products == []
    assert result.at_risk_products == []
    assert result.open_po_quantity == 40.0
    assert result.inbound_quantity == 0.0


def test_exposure_serializes_with_provenance():
    result = exposure.describe_supplier_exposure("S1", "Supplier One", [], [], [], None)
    payload = result.to_dict()
    assert payload["supplier_id"] == "S1"
    assert payload["supplier_name"] == "Supplier One"
    assert payload["affected_products"] == []
