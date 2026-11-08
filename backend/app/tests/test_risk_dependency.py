"""Phase 7 dependency risk tests (exposure, never diversification orders)."""

from backend.app.analytics.risk import dependency
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG

CONFIG = DEFAULT_RISK_CONFIG
DAY = "2026-06-30"


def test_single_supplier_dependency():
    record = dependency.product_dependency("P1", ["S1"], 2, DAY, CONFIG)
    assert record.severity == "HIGH"
    assert "single-supplier dependency" in record.explanation.lower()


def test_multiple_suppliers_low():
    record = dependency.product_dependency("P1", ["S1", "S2", "S3"], 0, DAY, CONFIG)
    assert record.severity == "LOW"
    assert record.metrics["supplier_count"] == 3.0


def test_supplier_concentration_fanout():
    record = dependency.supplier_fanout("S1", ["P1", "P2"], 4, DAY)
    assert record.severity == "HIGH"  # 2/4 >= 0.5
    record = dependency.supplier_fanout("S1", ["P1"], 4, DAY)
    assert record.severity == "MODERATE"
    record = dependency.supplier_fanout("S1", [], 4, DAY)
    assert record.severity == "LOW"


def test_warehouse_breadth():
    assert dependency.warehouse_breadth("W1", [], DAY).severity == "UNKNOWN"
    assert dependency.warehouse_breadth("W1", ["S1"], DAY).severity == "HIGH"
    assert dependency.warehouse_breadth("W1", ["S1", "S2"], DAY).severity == "MODERATE"
    assert dependency.warehouse_breadth("W1", ["S1", "S2", "S3"], DAY).severity == "LOW"


def test_no_supplier_history_unknown():
    record = dependency.product_dependency("P9", [], 0, DAY, CONFIG)
    assert record.severity == "UNKNOWN"
    assert "supplier_relationships" in record.missing_evidence


def test_no_diversification_language():
    record = dependency.product_dependency("P1", ["S1"], 1, DAY, CONFIG)
    lowered = (record.explanation + " ".join(record.evidence)).lower()
    for banned in ("add supplier", "diversify", "switch supplier", "alternate supplier"):
        assert banned not in lowered
