"""Phase 6 report assembly tests (structure, labeling, wording)."""

from datetime import date

from backend.app.analytics.procurement import reports
from backend.app.analytics.procurement.types import (
    DEFAULT_PROCUREMENT_CONFIG,
    DeliveryMetrics,
    ProcurementIntelligenceResult,
    ProcurementRiskSignal,
    SupplierExposure,
    SupplierPerformance,
)

ANALYSIS = date(2026, 6, 30)
CONFIG = DEFAULT_PROCUREMENT_CONFIG


def _result(supplier="S1", name="Supplier One", risk="MONITOR"):
    return ProcurementIntelligenceResult(
        supplier_id=supplier,
        supplier_name=name,
        analysis_date="2026-06-30",
        performance=SupplierPerformance(
            supplier_id=supplier, supplier_name=name,
            analysis_date="2026-06-30", po_count=3,
        ),
        delivery=DeliveryMetrics(supplier_id=supplier, reliability="STABLE", shipments=8),
        exposure=SupplierExposure(supplier_id=supplier, supplier_name=name),
        risk_signal=ProcurementRiskSignal(
            supplier_id=supplier, signal=risk, severity=risk.lower(), reason="test reason"
        ),
    )


def test_report_json_structure_and_labeling():
    report = reports.build_report(
        [_result()], [{"dimension": "supplier", "supplier_id": "S1",
                       "share": 0.6, "basis": "spend", "note": "n"}],
        {"SINGLE_SUPPLIER": ["P1"], "MULTI_SUPPLIER": [], "NO_SUPPLIER_HISTORY": []},
        [{"product_id": "P1", "warehouse_id": "W1", "state": "NO_KNOWN_INBOUND",
          "known_inbound": 0.0, "uncovered_demand": 10.0, "reason": "r"}],
        ANALYSIS, 28, {"start": "2025-07-01", "end": "2026-06-30"}, CONFIG,
    )
    assert report["synthetic"] is True
    assert "SYNTHETIC" in report["disclaimer"]
    assert report["analysis_date"] == "2026-06-30"
    assert report["forecast_horizon_days"] == 28
    assert report["risk_counts"] == {"MONITOR": 1}
    assert report["reliability_counts"] == {"STABLE": 1}
    assert len(report["limitations"]) >= 5
    assert all(item["synthetic"] is True for item in report["results"])


def test_markdown_sections_and_wording():
    report = reports.build_report(
        [_result("S1", "Supplier One", "ELEVATED")], [],
        {"SINGLE_SUPPLIER": [], "MULTI_SUPPLIER": ["P1"], "NO_SUPPLIER_HISTORY": []},
        [], ANALYSIS, 14, {"start": None, "end": None}, CONFIG,
    )
    markdown = reports.render_markdown(report)
    assert markdown.startswith("# SupplySense Nexus Supplier & Procurement Intelligence Report")
    assert "SYNTHETIC" in markdown
    for section in ("Supplier overview", "Supplier performance", "Lead-time intelligence",
                    "Delivery intelligence", "Supplier-product relationships",
                    "Open purchase orders", "Inbound coverage", "MOQ intelligence",
                    "Supplier concentration", "Single-supplier dependency",
                    "Inventory exposure by supplier", "Service exposure",
                    "Procurement risk signals", "Data quality", "Missing evidence",
                    "Limitations", "Per-supplier breakdown", "Per-product/supplier breakdown"):
        assert section in markdown
    lowered = markdown.lower()
    for banned in ("should be replaced", "switch to supplier",
                   "order 500 units", "diversify suppliers",
                   "you should buy", "optimal order quantity"):
        assert banned not in lowered


def test_empty_results_report():
    report = reports.build_report(
        [], [], {"SINGLE_SUPPLIER": [], "MULTI_SUPPLIER": [], "NO_SUPPLIER_HISTORY": []},
        [], ANALYSIS, 28, {"start": None, "end": None}, CONFIG,
    )
    assert report["results"] == []
    assert report["risk_counts"] == {}
    assert "SYNTHETIC" in reports.render_markdown(report)
