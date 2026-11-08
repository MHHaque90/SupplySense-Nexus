"""Phase 6 procurement risk signal tests (all states, no scores)."""

from backend.app.analytics.procurement import risk_signals
from backend.app.analytics.procurement.types import (
    DEFAULT_PROCUREMENT_CONFIG,
    DeliveryMetrics,
    OpenOrderMetrics,
    SupplierExposure,
)

CONFIG = DEFAULT_PROCUREMENT_CONFIG


def _delivery(reliability, late_rate=0.0, shipments=10):
    return DeliveryMetrics(
        supplier_id="S1", reliability=reliability, shipments=shipments,
        on_time=shipments, late=0, on_time_rate=1.0 - late_rate, late_rate=late_rate,
        evidence="test",
    )


def _exposure(**overrides):
    base = {"supplier_id": "S1", "supplier_name": "Supplier One"}
    base.update(overrides)
    return SupplierExposure(**base)


def _order(overdue=False, remaining=10.0):
    return OpenOrderMetrics(
        po_id="PO1", po_number="PO-001", supplier_id="S1", product_id="P1",
        order_date="2026-06-01", remaining_quantity=remaining, overdue=overdue,
    )


def test_no_signal_clean_supplier():
    signal = risk_signals.supplier_risk_signal(
        "S1", _delivery("STABLE"), _exposure(), [_order()], [], False, [], CONFIG
    )
    assert signal.signal == "NO_SIGNAL"
    assert signal.severity == "no_signal"
    for banned in ("ranking", "score", "best supplier", "replace", "switch"):
        assert banned not in signal.reason.lower()
        assert all(banned not in item.lower() for item in signal.evidence)


def test_unknown_without_evidence():
    signal = risk_signals.supplier_risk_signal(
        "S1", None, None, [], [], False, [], CONFIG
    )
    assert signal.signal == "UNKNOWN"
    assert "delivery_history" in signal.missing_evidence
    assert "inventory_exposure" in signal.missing_evidence


def test_monitor_variable_delivery():
    signal = risk_signals.supplier_risk_signal(
        "S1", _delivery("VARIABLE", late_rate=0.1), _exposure(), [], [], False, [], CONFIG
    )
    assert signal.signal == "MONITOR"


def test_elevated_delayed_and_single_supplier():
    signal = risk_signals.supplier_risk_signal(
        "S1", _delivery("DELAYED", late_rate=0.3),
        _exposure(at_risk_products=["P1"]), [], ["P1"], False, [], CONFIG
    )
    assert signal.signal == "ELEVATED"
    assert "P1" in signal.reason
    assert "replace" not in signal.reason.lower()
    assert "switch" not in signal.reason.lower()


def test_high_exposure_stockout_link():
    signal = risk_signals.supplier_risk_signal(
        "S1", _delivery("STABLE"), _exposure(stockout_products=["P1"]),
        [], [], False, [], CONFIG
    )
    assert signal.signal == "HIGH_EXPOSURE"
    assert signal.severity == "high_exposure"


def test_overdue_inbound_elevates():
    signal = risk_signals.supplier_risk_signal(
        "S1", _delivery("STABLE"), _exposure(), [_order(overdue=True)], [], False, [], CONFIG
    )
    assert signal.signal == "ELEVATED"
    assert signal.metrics["overdue_lines"] == 1.0


def test_high_uncertainty_and_concentration_evidence():
    signal = risk_signals.supplier_risk_signal(
        "S1", _delivery("STABLE"), _exposure(), [], [], True, ["P1"], CONFIG
    )
    assert signal.signal == "MONITOR"
    assert any("concentration" in item for item in signal.evidence)
    assert any("uncertainty" in item for item in signal.evidence)
    assert "diversify" not in " ".join(signal.evidence).lower()
