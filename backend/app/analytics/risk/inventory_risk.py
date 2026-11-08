"""Inventory risk domain (Phase 7).

Consumes Phase 5 inventory intelligence without overriding health
semantics: health states map transparently onto risk exposure, and a
broader interpretation (volatility, urgency, service warnings) is
layered alongside, never instead.
"""

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.risk.types import (
    RiskIntelligenceConfig,
    RiskRecord,
    max_severity,
    risk_id,
)

DOMAIN = "inventory"

_HEALTH_TO_EXPOSURE = {
    "STOCKOUT": "CRITICAL",
    "CRITICAL": "HIGH",
    "AT_RISK": "MODERATE",
    "HEALTHY": "LOW",
    "EXCESS": "LOW",
    "UNKNOWN": "UNKNOWN",
}


def assess(
    result: InventoryIntelligenceResult,
    config: RiskIntelligenceConfig,
) -> RiskRecord:
    """Assess inventory risk for one product/warehouse result."""
    entity = f"{result.product_id}|{result.warehouse_id}"
    missing: list[str] = list(result.health.missing_evidence) if result.health else []
    evidence: list[str] = []
    metrics: dict[str, float | None] = {}
    supporting: list[str] = [f"phase5:{entity}:{result.analysis_date}"]
    if result.position is None or result.position.unknown:
        return RiskRecord(
            risk_id=risk_id(DOMAIN, "product_warehouse", entity, result.analysis_date),
            domain=DOMAIN, entity_type="product_warehouse", entity_id=entity,
            product_id=result.product_id, warehouse_id=result.warehouse_id,
            analysis_date=result.analysis_date, state="UNKNOWN", severity="UNKNOWN",
            evidence=["No inventory position known at the analysis date."],
            missing_evidence=["inventory_position"] + missing,
            provenance=_provenance(result),
            explanation="Inventory risk is UNKNOWN because the position is unknown.",
        )
    health = result.health.health if result.health else "UNKNOWN"
    exposure = _HEALTH_TO_EXPOSURE.get(health, "UNKNOWN")
    evidence.append(f"Phase 5 health is {health}.")
    states = [exposure]
    on_hand = result.position.current_on_hand or 0.0
    metrics["on_hand"] = on_hand
    dos = result.coverage.forecast_days_of_supply if result.coverage else None
    if dos is not None:
        metrics["days_of_supply"] = dos
        evidence.append(f"Forecast days of supply is {dos:.1f}.")
        if dos <= config.critical_dos:
            states.append("HIGH")
            evidence.append("Days of supply at or below the critical threshold.")
        elif dos <= config.at_risk_dos:
            states.append("MODERATE")
    else:
        missing.append("days_of_supply")
    urgency = result.reorder.urgency if result.reorder else "unknown"
    if urgency == "urgent":
        states.append("HIGH")
        evidence.append("Reorder urgency is urgent.")
    elif urgency in ("plan", "monitor"):
        states.append("MODERATE")
    volatility = result.position.recent_volatility
    if volatility is not None:
        metrics["recent_volatility"] = volatility
    stockouts = result.position.stockout_observations
    metrics["stockout_observations"] = float(stockouts)
    if stockouts > 0:
        evidence.append(f"{stockouts} historical stockout observation(s).")
        states.append("MODERATE")
    if "service" in (result.service_note or "").lower() and "no repeated" not in (
        result.service_note or ""
    ).lower():
        states.append("MODERATE")
        evidence.append("Service evidence flags repeated recent stockouts.")
    severity = max_severity(states)
    if severity == "UNKNOWN":
        missing.append("coverage")
    return RiskRecord(
        risk_id=risk_id(DOMAIN, "product_warehouse", entity, result.analysis_date),
        domain=DOMAIN, entity_type="product_warehouse", entity_id=entity,
        product_id=result.product_id, warehouse_id=result.warehouse_id,
        analysis_date=result.analysis_date, state=severity, severity=severity,
        evidence=evidence, metrics=metrics, supporting_records=supporting,
        missing_evidence=missing,
        confidence=dict(result.forecast.confidence) if result.forecast else {},
        provenance=_provenance(result),
        explanation=(
            f"Inventory risk is {severity} for {entity}: "
            + " ".join(evidence[:2]) if evidence else
            f"Inventory risk is {severity} for {entity}."
        ),
    )


def _provenance(result: InventoryIntelligenceResult) -> dict[str, object]:
    """Carry Phase 5/4 provenance into the risk record."""
    forecast = result.forecast
    return {
        "phase5_health": result.health.health if result.health else None,
        "forecast_model": forecast.model_name if forecast else None,
        "forecast_origin": forecast.origin if forecast else None,
        "forecast_horizon": forecast.horizon if forecast else None,
        "validation_metric": forecast.validation_metric if forecast else None,
        "validation_score": forecast.validation_score if forecast else None,
        "forecast_confidence": dict(forecast.confidence) if forecast else {},
        "data_source": "synthetic",
    }
