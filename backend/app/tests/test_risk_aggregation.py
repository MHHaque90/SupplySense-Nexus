"""Phase 7 aggregation, explanations, and register tests."""

from backend.app.analytics.risk import aggregation, register, risk_explanations
from backend.app.analytics.risk.types import RiskRecord


def _record(domain, severity, entity="P1|W1", evidence=("observed evidence",)):
    return RiskRecord(
        risk_id=f"{domain}:{entity}", domain=domain, entity_type="product_warehouse",
        entity_id=entity, analysis_date="2026-06-30",
        state=severity, severity=severity, evidence=list(evidence),
    )


def test_series_aggregation_takes_max():
    records = [_record("inventory", "MODERATE"), _record("service", "LOW")]
    overall = aggregation.aggregate_series("P1", "W1", "2026-06-30", records)
    assert overall.severity == "MODERATE"
    assert overall.domain == "overall"
    assert len(overall.supporting_records) == 2
    assert "Descriptive combination only" in overall.explanation


def test_combination_boost_documented():
    inventory = _record("inventory", "HIGH", evidence=("projected stockout in 2 days",))
    inbound = _record("inbound", "HIGH", evidence=("shortfall of 40 units",))
    supplier = _record("supplier", "HIGH")
    dependency = _record("dependency", "HIGH")
    leadtime = _record("leadtime", "MODERATE")
    overall = aggregation.aggregate_series(
        "P1", "W1", "2026-06-30", [inventory, inbound, supplier, dependency, leadtime]
    )
    assert overall.severity == "HIGH"
    assert any("Combined exposure pattern" in item for item in overall.evidence)


def test_empty_aggregation_unknown():
    overall = aggregation.aggregate_series("P1", "W1", "2026-06-30", [])
    assert overall.severity == "UNKNOWN"
    assert "component_risks" in overall.missing_evidence


def test_supplier_aggregation_transparent():
    records = [_record("supplier", "ELEVATED"), _record("procurement", "MONITOR")]
    overall = aggregation.aggregate_supplier("S1", "2026-06-30", records)
    assert overall.severity == "ELEVATED"
    assert overall.supplier_id == "S1"


def test_explanations_have_no_prescriptions():
    text = risk_explanations.explain_overall("P1|W1", "HIGH", [_record("inventory", "HIGH")])
    lowered = text.lower()
    for banned in ("switch", "order more", "expedite", "cancel", "recommend", "should"):
        assert banned not in lowered
    assert "no action is implied" in lowered


def test_register_filters():
    records = [
        _record("inventory", "HIGH"),
        _record("supplier", "LOW"),
        RiskRecord(risk_id="s", domain="supplier", entity_type="supplier",
                   entity_id="S1", supplier_id="S1", analysis_date="2026-06-30",
                   state="UNKNOWN", severity="UNKNOWN"),
    ]
    assert len(register.filter_records(records, severity="HIGH")) == 1
    assert len(register.filter_records(records, domain="supplier")) == 2
    assert len(register.filter_records(records, include_unknown=False)) == 2
    assert len(register.filter_records(records, supplier_id="S1")) == 1
    assert register.to_dict_list(records[:1])[0]["risk_id"] == "inventory:P1|W1"
