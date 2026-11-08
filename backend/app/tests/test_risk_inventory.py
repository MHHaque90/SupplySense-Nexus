"""Phase 7 inventory risk domain tests."""

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.inventory.types import (
    CoverageResult,
    InventoryHealth,
    InventoryPosition,
    ReorderSignal,
    StockoutExposure,
)
from backend.app.analytics.risk import inventory_risk
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG

CONFIG = DEFAULT_RISK_CONFIG


def _result(health="HEALTHY", on_hand=100.0, dos=20.0, urgency="no_signal"):
    return InventoryIntelligenceResult(
        product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
        position=InventoryPosition(
            product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
            current_on_hand=on_hand, latest_snapshot_date="2026-06-30",
            recent_volatility=5.0, stockout_observations=0,
        ),
        coverage=CoverageResult(
            product_id="P1", warehouse_id="W1",
            forecast_days_of_supply=dos, forecast_days_of_supply_state="finite",
        ),
        stockout=StockoutExposure(product_id="P1", warehouse_id="W1", exposure="no_exposure"),
        health=InventoryHealth(product_id="P1", warehouse_id="W1",
                               health=health, reason="test"),
        reorder=ReorderSignal(product_id="P1", warehouse_id="W1", urgency=urgency),
    )


def test_projected_stockout_maps_to_critical():
    record = inventory_risk.assess(_result("STOCKOUT", on_hand=0.0), CONFIG)
    assert record.severity == "CRITICAL"
    assert record.domain == "inventory"
    assert "STOCKOUT" in record.evidence[0]


def test_low_dos_band():
    record = inventory_risk.assess(_result("HEALTHY", on_hand=10.0, dos=2.0), CONFIG)
    assert record.severity == "HIGH"
    assert any("critical threshold" in item for item in record.evidence)


def test_healthy_inventory_maps_low():
    record = inventory_risk.assess(_result(), CONFIG)
    assert record.severity == "LOW"
    assert record.metrics["on_hand"] == 100.0


def test_unknown_inventory_evidence():
    result = _result("UNKNOWN", on_hand=None)
    result.position.unknown = True
    record = inventory_risk.assess(result, CONFIG)
    assert record.severity == "UNKNOWN"
    assert "inventory_position" in record.missing_evidence
    assert record.explanation.startswith("Inventory risk is UNKNOWN")


def test_traceability_fields():
    record = inventory_risk.assess(_result(), CONFIG)
    assert record.product_id == "P1" and record.warehouse_id == "W1"
    assert record.analysis_date == "2026-06-30"
    assert record.synthetic is True
    assert record.supporting_records == ["phase5:P1|W1:2026-06-30"]
    assert record.provenance["data_source"] == "synthetic"
