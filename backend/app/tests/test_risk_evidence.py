"""Phase 7 evidence model tests (UNKNOWN never means LOW)."""

from backend.app.analytics.risk import evidence
from backend.app.analytics.risk.types import RiskRecord, max_severity, risk_id


def test_missing_evidence_records_stay_unknown():
    records = evidence.assess_gaps(
        "supplier", "S1", "2026-06-30",
        ["delivery_history", "delivery_history", "open_procurement"],
        supplier_id="S1",
    )
    assert len(records) == 2  # deduplicated
    assert all(record.severity == "UNKNOWN" for record in records)
    assert all("never implies low risk" in record.explanation.lower() for record in records)
    assert records[0].missing_evidence == ["delivery_history"]


def test_no_gaps_no_records():
    assert evidence.assess_gaps("supplier", "S1", "2026-06-30", []) == []


def test_risk_id_deterministic():
    first = risk_id("inventory", "product_warehouse", "P1|W1", "2026-06-30")
    assert first == risk_id("inventory", "product_warehouse", "P1|W1", "2026-06-30")
    assert first == "inventory:product_warehouse:P1|W1:2026-06-30"


def test_max_severity_ordering():
    assert max_severity(["LOW", "HIGH", "MODERATE"]) == "HIGH"
    assert max_severity(["UNKNOWN", "UNKNOWN"]) == "UNKNOWN"
    assert max_severity([]) == "UNKNOWN"
    assert max_severity(["UNKNOWN", "LOW"]) == "LOW"


def test_record_serializes_with_provenance():
    record = RiskRecord(
        risk_id="r1", domain="inventory", entity_type="product_warehouse",
        entity_id="P1|W1", analysis_date="2026-06-30",
        state="LOW", severity="LOW", synthetic=True,
    )
    payload = record.to_dict()
    assert payload["synthetic"] is True
    assert payload["missing_evidence"] == []
    assert payload["evidence"] == []
