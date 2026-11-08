"""Phase 6 concentration and dependency tests."""

import pandas as pd

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.inventory.types import InventoryHealth
from backend.app.analytics.procurement import concentration
from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG


def _lines():
    return pd.DataFrame({
        "supplier_id": ["S1", "S1", "S2"],
        "po_id": ["PO1", "PO2", "PO3"],
        "product_id": ["P1", "P2", "P1"],
        "line_total": [1000.0, 500.0, 500.0],
        "quantity": [100.0, 50.0, 25.0],
    })


def _links():
    return pd.DataFrame({
        "supplier_id": ["S1", "S1", "S2", "S2"],
        "product_id": ["P1", "P2", "P1", "P3"],
    })


def test_supplier_spend_and_quantity_shares():
    spend = {row.supplier_id: row.share for row in concentration.volume_shares(_lines(), "spend")}
    assert spend == {"S1": 0.75, "S2": 0.25}
    quantity = {row.supplier_id: row.share for row in concentration.volume_shares(_lines(), "quantity")}
    assert quantity["S1"] == 150.0 / 175.0
    assert concentration.volume_shares(_lines().iloc[0:0], "spend") == []


def test_po_count_shares():
    shares = {row.supplier_id: row.share for row in concentration.po_count_shares(_lines())}
    assert shares["S1"] == 2 / 3
    assert shares["S2"] == 1 / 3


def test_single_supplier_dependency():
    classes = concentration.dependency_classes(_links())
    assert classes["SINGLE_SUPPLIER"] == ["P2", "P3"]
    assert classes["MULTI_SUPPLIER"] == ["P1"]
    assert classes["NO_SUPPLIER_HISTORY"] == []
    assert concentration.dependency_classes(pd.DataFrame()) == {
        "SINGLE_SUPPLIER": [], "MULTI_SUPPLIER": [], "NO_SUPPLIER_HISTORY": []
    }


def test_category_concentration():
    rows = concentration.category_concentration(_lines(), {"P1": "Cat", "P2": "Cat"})
    assert len(rows) == 1
    assert rows[0].supplier_id == "S1"
    assert rows[0].share == 1500.0 / 2000.0


def test_exposure_concentration_links_suppliers():
    intelligence = [
        InventoryIntelligenceResult(
            product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
            health=InventoryHealth(product_id="P1", warehouse_id="W1",
                                   health="AT_RISK", reason="test"),
        ),
        InventoryIntelligenceResult(
            product_id="P2", warehouse_id="W1", analysis_date="2026-06-30",
            health=InventoryHealth(product_id="P2", warehouse_id="W1",
                                   health="HEALTHY", reason="test"),
        ),
    ]
    mapping = {"S1": {"P1", "P2"}, "S2": {"P1"}}
    rows = {row.supplier_id: row.share for row in concentration.exposure_concentration(
        intelligence, mapping, DEFAULT_PROCUREMENT_CONFIG
    )}
    assert rows == {"S1": 1.0, "S2": 1.0}
    healthy_only = [intelligence[1]]
    assert concentration.exposure_concentration(
        healthy_only, mapping, DEFAULT_PROCUREMENT_CONFIG
    ) == []
