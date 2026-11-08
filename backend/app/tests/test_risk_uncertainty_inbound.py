"""Phase 7 uncertainty and inbound risk tests."""

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.inventory.types import ForecastInput
from backend.app.analytics.procurement.types import InboundCoverage
from backend.app.analytics.risk import inbound_risk, uncertainty_risk
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG

CONFIG = DEFAULT_RISK_CONFIG


def _result(point, width_factor=0.2, confidence="strong validation support"):
    total = len(point)
    width = [value * width_factor for value in point]
    lower = [max(0.0, value - half) for value, half in zip(point, width)]
    upper = [value + half for value, half in zip(point, width)]
    return InventoryIntelligenceResult(
        product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
        forecast=ForecastInput(
            product_id="P1", warehouse_id="W1", origin="2026-06-30",
            forecast_dates=[f"2026-07-{day:02d}" for day in range(1, total + 1)],
            horizon=total, point=list(point), lower=lower, upper=upper,
            confidence={"level": confidence},
        ),
    )


def test_high_interval_width():
    record = uncertainty_risk.assess(_result([10.0] * 10, width_factor=1.5), CONFIG)
    assert record.severity == "HIGH"


def test_low_confidence_moderate():
    record = uncertainty_risk.assess(
        _result([10.0] * 10, width_factor=0.1, confidence="limited validation support"),
        CONFIG,
    )
    assert record.severity == "MODERATE"


def test_low_uncertainty():
    record = uncertainty_risk.assess(_result([10.0] * 10, width_factor=0.1), CONFIG)
    assert record.severity == "LOW"


def test_missing_forecast_unknown():
    result = _result([10.0] * 5)
    result.forecast.missing = True
    result.forecast.point = []
    record = uncertainty_risk.assess(result, CONFIG)
    assert record.severity == "UNKNOWN"
    assert "forecast" in record.missing_evidence


def test_inbound_supported_low():
    coverage = InboundCoverage(product_id="P1", warehouse_id="W1",
                               state="INBOUND_SUPPORTED", known_inbound=50.0,
                               uncovered_demand=0.0)
    result = _result([10.0] * 5)
    record = inbound_risk.assess(result, coverage, CONFIG)
    assert record.severity == "LOW"


def test_inbound_insufficient_high():
    coverage = InboundCoverage(product_id="P1", warehouse_id="W1",
                               state="INBOUND_INSUFFICIENT", known_inbound=10.0,
                               uncovered_demand=40.0)
    result = _result([10.0] * 5)
    record = inbound_risk.assess(result, coverage, CONFIG)
    assert record.severity == "HIGH"
    assert record.metrics["uncovered_demand"] == 40.0


def test_inbound_partial_moderate():
    coverage = InboundCoverage(product_id="P1", warehouse_id="W1", state="INBOUND_PARTIAL")
    result = _result([10.0] * 5)
    record = inbound_risk.assess(result, coverage, CONFIG)
    assert record.severity == "MODERATE"


def test_inbound_unknown_missing():
    result = _result([10.0] * 5)
    record = inbound_risk.assess(result, None, CONFIG)
    assert record.severity == "UNKNOWN"
    assert "inbound_coverage" in record.missing_evidence
