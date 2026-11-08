"""Phase 7 report assembly tests (structure, labeling, wording)."""

from datetime import date

from backend.app.analytics.risk import reports
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG, RiskRecord

ANALYSIS = date(2026, 6, 30)


def _record(domain="inventory", severity="HIGH", entity="P1|W1"):
    return RiskRecord(
        risk_id=f"{domain}:{entity}:2026-06-30", domain=domain,
        entity_type="product_warehouse", entity_id=entity,
        product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
        state=severity, severity=severity,
        evidence=[f"{domain} evidence observed."],
        explanation=f"{domain} risk is {severity}.",
    )


def test_report_json_structure_and_labeling():
    report = reports.build_report(
        [_record(), _record("supplier", "MODERATE", "S1")],
        ANALYSIS, 28, {"start": "2025-07-01", "end": "2026-06-30"},
        DEFAULT_RISK_CONFIG,
    )
    assert report["synthetic"] is True
    assert "SYNTHETIC" in report["disclaimer"]
    assert report["analysis_date"] == "2026-06-30"
    assert report["forecast_horizon_days"] == 28
    assert set(report["risk_by_domain"]) == {"inventory", "supplier"}
    assert len(report["register"]) == 2
    assert len(report["limitations"]) >= 5
    assert all(item["synthetic"] is True for item in report["register"])


def test_markdown_sections_and_wording():
    report = reports.build_report(
        [_record("inventory", "CRITICAL"), _record("evidence", "UNKNOWN")],
        ANALYSIS, 14, {"start": None, "end": None}, DEFAULT_RISK_CONFIG,
    )
    markdown = reports.render_markdown(report)
    assert markdown.startswith("# SupplySense Nexus Supply-Chain Risk Intelligence Report")
    assert "SYNTHETIC" in markdown
    for section in ("Risk overview", "Inventory risk", "Supplier risk",
                    "Procurement risk", "Dependency risk", "Service risk",
                    "Concentration risk", "Lead-time risk",
                    "Forecast uncertainty risk", "Inbound exposure risk",
                    "Data/evidence risk", "Risk register", "Highest-exposure entities",
                    "Supplier exposure", "Product exposure", "Warehouse exposure",
                    "Missing evidence", "Data quality", "Limitations",
                    "Phase 8 handoff"):
        assert section in markdown
    lowered = markdown.lower()
    for banned in ("should switch supplier", "should replace supplier",
                   "best supplier", "worst supplier", "recommended supplier",
                   "buy from", "order more", "order less", "expedite",
                   "cancel po", "diversify suppliers", "transfer inventory",
                   "optimal supplier", "optimal quantity", "optimal decision"):
        assert banned not in lowered


def test_empty_report():
    report = reports.build_report([], ANALYSIS, 28, {"start": None, "end": None},
                                  DEFAULT_RISK_CONFIG)
    assert report["risk_overview"]["records"] == 0
    assert "SYNTHETIC" in reports.render_markdown(report)


def test_highest_exposure_ordered():
    records = [_record("inventory", "LOW"), _record("supplier", "HIGH", "S1")]
    report = reports.build_report(records, ANALYSIS, 28, {"start": None, "end": None},
                                  DEFAULT_RISK_CONFIG)
    assert report["highest_exposure"][0]["severity"] == "HIGH"
