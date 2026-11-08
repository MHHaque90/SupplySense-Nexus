"""Phase 7 procurement risk domain tests."""

from backend.app.analytics.procurement.types import (
    OpenOrderMetrics,
    ProcurementIntelligenceResult,
)
from backend.app.analytics.risk import procurement_risk
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG

CONFIG = DEFAULT_RISK_CONFIG


def _order(overdue=False, remaining=10.0):
    return OpenOrderMetrics(
        po_id="PO1", po_number="PO-001", supplier_id="S1", product_id="P1",
        order_date="2026-06-01", remaining_quantity=remaining, overdue=overdue,
    )


def _result(orders):
    return ProcurementIntelligenceResult(
        supplier_id="S1", supplier_name="Supplier One",
        analysis_date="2026-06-30", open_orders=list(orders),
    )


def test_overdue_inbound_elevated():
    record = procurement_risk.assess(_result([_order(overdue=True)]), CONFIG)
    assert record.severity == "ELEVATED"
    assert record.metrics["overdue_lines"] == 1.0


def test_insufficient_inbound_monitor():
    record = procurement_risk.assess(_result([_order()]), CONFIG)
    assert record.severity == "NO_SIGNAL"


def test_open_orders_without_issues_no_signal():
    record = procurement_risk.assess(_result([_order(), _order()]), CONFIG)
    assert record.severity == "NO_SIGNAL"
    assert record.metrics["open_lines"] == 2.0


def test_no_known_inbound_unknown():
    record = procurement_risk.assess(_result([]), CONFIG)
    assert record.severity == "UNKNOWN"
    assert "open_procurement" in record.missing_evidence
