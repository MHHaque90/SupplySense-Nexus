"""Phase 7 service risk tests (association only, never causality)."""

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.inventory.types import InventoryHealth, InventoryPosition
from backend.app.analytics.procurement.types import ServiceExposure
from backend.app.analytics.risk import service_risk
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG

CONFIG = DEFAULT_RISK_CONFIG


def _result(stockouts=0, note="No repeated recent stockouts."):
    return InventoryIntelligenceResult(
        product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
        position=InventoryPosition(
            product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
            current_on_hand=50.0, latest_snapshot_date="2026-06-30",
            stockout_observations=stockouts,
        ),
        health=InventoryHealth(product_id="P1", warehouse_id="W1",
                               health="HEALTHY", reason="test"),
        service_note=note,
    )


def _cooccurrence():
    return [ServiceExposure(
        supplier_id="S1", product_id="P1", warehouse_id="W1",
        delayed_shipments=2, service_flag="AT_RISK",
        description="test association",
    )]


def test_repeated_stockouts_high():
    record = service_risk.assess(_result(stockouts=3), [], CONFIG)
    assert record.severity == "HIGH"


def test_service_warning_moderate():
    record = service_risk.assess(
        _result(stockouts=0, note="2 stockout observations; repeated recent stockouts flagged."),
        [], CONFIG,
    )
    assert record.severity == "MODERATE"


def test_supplier_delay_association_moderate():
    record = service_risk.assess(_result(), _cooccurrence(), CONFIG)
    assert record.severity == "MODERATE"
    assert "during a period containing" in record.evidence[0]
    assert "caused" not in " ".join(record.evidence).lower()


def test_healthy_service_low():
    record = service_risk.assess(_result(), [], CONFIG)
    assert record.severity == "LOW"


def test_missing_service_history_unknown():
    result = _result()
    result.position.unknown = True
    result.position.current_on_hand = None
    record = service_risk.assess(result, [], CONFIG)
    assert record.severity == "UNKNOWN"
    assert "service_history" in record.missing_evidence
