"""Lead-time risk domain (Phase 7).

Consumes observed Phase 6 lead-time metrics. Describes evidence and
sample sufficiency; never forecasts future lead times and never builds
a lead-time model.
"""

from backend.app.analytics.procurement.types import LeadTimeMetrics
from backend.app.analytics.risk.types import (
    RiskIntelligenceConfig,
    RiskRecord,
    max_severity,
    risk_id,
)

DOMAIN = "leadtime"


def assess(
    metrics: LeadTimeMetrics,
    analysis_date: str,
    config: RiskIntelligenceConfig,
) -> RiskRecord:
    """Assess lead-time risk for one supplier/product relationship."""
    entity = f"{metrics.supplier_id}|{metrics.product_id}"
    evidence: list[str] = []
    states: list[str] = []
    record_metrics: dict[str, float | None] = {
        "observations": float(metrics.observations),
        "average_observed_days": metrics.average_observed_days,
        "std_observed_days": metrics.std_observed_days,
        "delay_frequency": metrics.delay_frequency,
    }
    if metrics.observations < config.min_shipments:
        return RiskRecord(
            risk_id=risk_id(DOMAIN, "supplier_product", entity, analysis_date),
            domain=DOMAIN, entity_type="supplier_product", entity_id=entity,
            supplier_id=metrics.supplier_id, product_id=metrics.product_id,
            analysis_date=analysis_date, state="UNKNOWN", severity="UNKNOWN",
            evidence=[f"Only {metrics.observations} lead-time observations."],
            missing_evidence=["lead_time_history"],
            provenance={"data_source": "synthetic"},
            explanation="Lead-time risk is UNKNOWN: insufficient observations.",
        )
    if metrics.delay_frequency is not None:
        evidence.append(f"Delay frequency is {metrics.delay_frequency:.2f}.")
        if metrics.delay_frequency >= config.high_delay_rate:
            states.append("HIGH")
        elif metrics.delay_frequency >= config.delayed_rate:
            states.append("MODERATE")
        else:
            states.append("LOW")
    if (metrics.std_observed_days or 0.0) >= config.variable_delay_std:
        states.append("MODERATE")
        evidence.append("High lead-time variability.")
    if metrics.average_observed_days is not None:
        evidence.append(f"Average observed lead time is {metrics.average_observed_days:.1f} days.")
    severity = max_severity(states) if states else "LOW"
    if not states:
        evidence.append("No adverse lead-time evidence observed.")
    return RiskRecord(
        risk_id=risk_id(DOMAIN, "supplier_product", entity, analysis_date),
        domain=DOMAIN, entity_type="supplier_product", entity_id=entity,
        supplier_id=metrics.supplier_id, product_id=metrics.product_id,
        analysis_date=analysis_date, state=severity, severity=severity,
        evidence=evidence, metrics=record_metrics,
        supporting_records=[f"leadtime:{entity}"],
        provenance={"data_source": "synthetic"},
        explanation=f"Lead-time risk is {severity} for {entity}.",
    )
