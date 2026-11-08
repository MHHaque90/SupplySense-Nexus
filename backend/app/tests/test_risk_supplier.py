"""Phase 7 supplier risk domain tests (descriptive, never ranked)."""

from backend.app.analytics.procurement.types import (
    DeliveryMetrics,
    ProcurementIntelligenceResult,
    SupplierExposure,
    SupplierPerformance,
)
from backend.app.analytics.risk import supplier_risk
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG

CONFIG = DEFAULT_RISK_CONFIG


def _result(reliability="STABLE", late_rate=0.0, shipments=10, exposed=(), stocked=()):
    return ProcurementIntelligenceResult(
        supplier_id="S1", supplier_name="Supplier One", analysis_date="2026-06-30",
        performance=SupplierPerformance(
            supplier_id="S1", supplier_name="Supplier One",
            analysis_date="2026-06-30", lead_time_std=2.0,
        ),
        delivery=DeliveryMetrics(
            supplier_id="S1", reliability=reliability, shipments=shipments,
            late_rate=late_rate, evidence="test",
        ),
        exposure=SupplierExposure(
            supplier_id="S1", supplier_name="Supplier One",
            at_risk_products=list(exposed), stockout_products=list(stocked),
        ),
    )


def test_high_delay_rate():
    record = supplier_risk.assess(_result("HIGH_DELAY", late_rate=0.6), CONFIG)
    assert record.severity == "HIGH"
    assert "best" not in record.explanation.lower()
    assert "worst" not in record.explanation.lower()


def test_variable_lead_time():
    result = _result("VARIABLE", late_rate=0.1)
    result.performance.lead_time_std = 9.0
    record = supplier_risk.assess(result, CONFIG)
    assert record.severity == "MODERATE"


def test_insufficient_observations_unknown():
    record = supplier_risk.assess(_result("UNKNOWN", shipments=2), CONFIG)
    assert record.severity == "UNKNOWN"
    assert "sufficient_shipment_history" in record.missing_evidence


def test_unknown_supplier_history():
    result = ProcurementIntelligenceResult(
        supplier_id="S9", supplier_name="Nobody", analysis_date="2026-06-30"
    )
    record = supplier_risk.assess(result, CONFIG)
    assert record.severity == "UNKNOWN"


def test_linked_stockout_exposure():
    record = supplier_risk.assess(
        _result("STABLE", stocked=("P1",)), CONFIG
    )
    assert record.severity == "HIGH"
    assert "P1" in record.evidence[-1]
