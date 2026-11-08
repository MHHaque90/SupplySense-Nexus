"""Phase 6 service co-occurrence tests (association, never causality)."""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.inventory.types import InventoryHealth, StockoutExposure
from backend.app.analytics.procurement import service_impact

ANALYSIS = date(2026, 6, 30)


def _shipments():
    return pd.DataFrame({
        "shipment_id": ["SH1", "SH2"],
        "po_id": ["PO1", "PO1"],
        "supplier_id": ["S1", "S1"],
        "expected_arrival_date": [date(2026, 5, 1), date(2026, 5, 10)],
        "actual_arrival_date": [date(2026, 5, 5), date(2026, 5, 10)],
        "delay_days": [4.0, 0.0],
    })


def _intelligence(health="AT_RISK", exposure="watch"):
    return [InventoryIntelligenceResult(
        product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
        health=InventoryHealth(product_id="P1", warehouse_id="W1",
                               health=health, reason="test"),
        stockout=StockoutExposure(product_id="P1", warehouse_id="W1", exposure=exposure),
    )]


def test_delay_service_cooccurrence_wording():
    results = service_impact.describe_cooccurrence(
        "S1", _shipments(), _intelligence(), ANALYSIS
    )
    assert len(results) == 1
    assert results[0].delayed_shipments == 1
    assert "no causality is claimed" in results[0].description.lower()
    assert "caused" not in results[0].description.lower()


def test_no_delays_no_cooccurrence():
    shipments = _shipments()
    shipments["delay_days"] = 0.0
    assert service_impact.describe_cooccurrence(
        "S1", shipments, _intelligence(), ANALYSIS
    ) == []


def test_healthy_series_excluded():
    assert service_impact.describe_cooccurrence(
        "S1", _shipments(), _intelligence("HEALTHY", "no_exposure"), ANALYSIS
    ) == []
