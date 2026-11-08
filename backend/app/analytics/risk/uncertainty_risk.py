"""Forecast uncertainty risk domain (Phase 7).

Consumes Phase 5 forecast uncertainty (interval width, confidence,
validation support) without recomputing Phase 4 intervals. Bounds are
never treated as guaranteed worst/best cases.
"""

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.risk.types import (
    RiskIntelligenceConfig,
    RiskRecord,
    max_severity,
    risk_id,
)

DOMAIN = "uncertainty"


def assess(
    result: InventoryIntelligenceResult,
    config: RiskIntelligenceConfig,
) -> RiskRecord:
    """Assess forecast-uncertainty risk for one product/warehouse result."""
    entity = f"{result.product_id}|{result.warehouse_id}"
    forecast = result.forecast
    if forecast is None or forecast.missing or not forecast.point:
        return RiskRecord(
            risk_id=risk_id(DOMAIN, "product_warehouse", entity, result.analysis_date),
            domain=DOMAIN, entity_type="product_warehouse", entity_id=entity,
            product_id=result.product_id, warehouse_id=result.warehouse_id,
            analysis_date=result.analysis_date, state="UNKNOWN", severity="UNKNOWN",
            evidence=["No forecast available for uncertainty assessment."],
            missing_evidence=["forecast"],
            provenance={"data_source": "synthetic"},
            explanation="Uncertainty risk is UNKNOWN without a forecast.",
        )
    widths = [hi - lo for hi, lo in zip(forecast.upper, forecast.lower)]
    mean_width = sum(widths) / len(widths)
    mean_point = sum(forecast.point) / len(forecast.point)
    spread = (mean_width / mean_point) if mean_point > 0 else 0.0
    confidence = forecast.confidence.get("level", "")
    states: list[str] = []
    evidence = [f"Mean interval width {mean_width:.1f} (spread {spread:.2f})."]
    if spread >= config.wide_interval_spread:
        states.append("HIGH")
        evidence.append("Wide intervals relative to mean demand.")
    elif spread >= config.wide_interval_spread / 2:
        states.append("MODERATE")
    else:
        states.append("LOW")
    if confidence == "limited validation support":
        states.append("MODERATE")
        evidence.append("Limited validation support for the selected model.")
    elif confidence == "insufficient evidence":
        return RiskRecord(
            risk_id=risk_id(DOMAIN, "product_warehouse", entity, result.analysis_date),
            domain=DOMAIN, entity_type="product_warehouse", entity_id=entity,
            product_id=result.product_id, warehouse_id=result.warehouse_id,
            analysis_date=result.analysis_date, state="UNKNOWN", severity="UNKNOWN",
            evidence=["Forecast confidence has insufficient evidence."],
            missing_evidence=["validation_support"],
            provenance=_provenance(forecast),
            explanation="Uncertainty risk is UNKNOWN: validation support insufficient.",
        )
    severity = max_severity(states)
    return RiskRecord(
        risk_id=risk_id(DOMAIN, "product_warehouse", entity, result.analysis_date),
        domain=DOMAIN, entity_type="product_warehouse", entity_id=entity,
        product_id=result.product_id, warehouse_id=result.warehouse_id,
        analysis_date=result.analysis_date, state=severity, severity=severity,
        evidence=evidence,
        metrics={"mean_interval_width": mean_width, "spread": spread},
        supporting_records=[f"phase5:{entity}:{result.analysis_date}"],
        provenance=_provenance(forecast),
        explanation=f"Forecast-uncertainty risk is {severity} for {entity}.",
    )


def _provenance(forecast) -> dict[str, object]:
    """Carry Phase 4 forecast provenance into the risk record."""
    return {
        "forecast_model": forecast.model_name,
        "forecast_origin": forecast.origin,
        "forecast_horizon": forecast.horizon,
        "validation_metric": forecast.validation_metric,
        "validation_score": forecast.validation_score,
        "data_source": "synthetic",
    }
