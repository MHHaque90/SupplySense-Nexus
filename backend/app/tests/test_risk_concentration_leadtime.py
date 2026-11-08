"""Phase 7 concentration and lead-time risk tests."""

from backend.app.analytics.procurement.types import LeadTimeMetrics, SupplierConcentration
from backend.app.analytics.risk import concentration_risk, leadtime_risk
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG

CONFIG = DEFAULT_RISK_CONFIG
DAY = "2026-06-30"


def _share(share, supplier="S1"):
    return SupplierConcentration(
        dimension="supplier", supplier_id=supplier, share=share,
        basis="spend", note="test",
    )


def test_concentration_states():
    assert concentration_risk.assess([_share(0.8)], DAY, CONFIG)[0].severity == "HIGH"
    assert concentration_risk.assess([_share(0.6)], DAY, CONFIG)[0].severity == "MODERATE"
    assert concentration_risk.assess([_share(0.2)], DAY, CONFIG)[0].severity == "LOW"


def test_concentration_unknown_share():
    rows = [SupplierConcentration(dimension="supplier", supplier_id="S1", share=None,
                                  basis="spend", note="test")]
    record = concentration_risk.assess(rows, DAY, CONFIG)[0]
    assert record.severity == "UNKNOWN"
    assert "concentration_basis" in record.missing_evidence


def test_concentration_empty_rows():
    records = concentration_risk.assess([], DAY, CONFIG)
    assert len(records) == 1 and records[0].severity == "UNKNOWN"


def test_concentration_highest():
    rows = [_share(0.2, "S1"), _share(0.8, "S2")]
    assert concentration_risk.highest(
        concentration_risk.assess(rows, DAY, CONFIG)
    ) == "HIGH"


def _leadtime(delay_frequency=0.0, std=1.0, observations=10):
    return LeadTimeMetrics(
        supplier_id="S1", product_id="P1", observations=observations,
        average_observed_days=12.0, std_observed_days=std,
        delay_frequency=delay_frequency,
    )


def test_leadtime_risk_bands():
    assert leadtime_risk.assess(_leadtime(0.0, 1.0), DAY, CONFIG).severity == "LOW"
    assert leadtime_risk.assess(_leadtime(0.3, 1.0), DAY, CONFIG).severity == "MODERATE"
    assert leadtime_risk.assess(_leadtime(0.7, 1.0), DAY, CONFIG).severity == "HIGH"
    assert leadtime_risk.assess(_leadtime(0.0, 9.0), DAY, CONFIG).severity == "MODERATE"


def test_leadtime_insufficient_sample_unknown():
    record = leadtime_risk.assess(_leadtime(0.0, 1.0, observations=2), DAY, CONFIG)
    assert record.severity == "UNKNOWN"
    assert "lead_time_history" in record.missing_evidence
