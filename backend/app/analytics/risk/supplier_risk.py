"""Supplier risk domain (Phase 7).

Consumes Phase 6 supplier performance, delivery, and exposure outputs.
Classifications are descriptive evidence bands, never global rankings
and never best/worst labels.
"""

from backend.app.analytics.procurement.types import ProcurementIntelligenceResult
from backend.app.analytics.risk.types import (
    SUPPLIER_SEVERITY_ORDER,
    RiskIntelligenceConfig,
    RiskRecord,
    max_severity,
    risk_id,
)

DOMAIN = "supplier"


def assess(
    result: ProcurementIntelligenceResult,
    config: RiskIntelligenceConfig,
) -> RiskRecord:
    """Assess supplier risk for one supplier result."""
    missing: list[str] = []
    if result.performance is not None:
        missing.extend(result.performance.missing_evidence)
    if result.delivery is not None and result.delivery.missing_evidence:
        missing.extend(result.delivery.missing_evidence)
    evidence: list[str] = []
    metrics: dict[str, float | None] = {}
    supporting: list[str] = [f"phase6:{result.supplier_id}:{result.analysis_date}"]
    states: list[str] = []
    performance = result.performance
    delivery = result.delivery
    if performance is None or delivery is None:
        return RiskRecord(
            risk_id=risk_id(DOMAIN, "supplier", result.supplier_id, result.analysis_date),
            domain=DOMAIN, entity_type="supplier", entity_id=result.supplier_id,
            supplier_id=result.supplier_id, analysis_date=result.analysis_date,
            state="UNKNOWN", severity="UNKNOWN",
            evidence=["No supplier performance evidence available."],
            missing_evidence=["supplier_performance"] + missing,
            provenance=_provenance(result),
            explanation="Supplier risk is UNKNOWN for lack of evidence.",
        )
    if delivery.shipments < config.min_shipments:
        return RiskRecord(
            risk_id=risk_id(DOMAIN, "supplier", result.supplier_id, result.analysis_date),
            domain=DOMAIN, entity_type="supplier", entity_id=result.supplier_id,
            supplier_id=result.supplier_id, analysis_date=result.analysis_date,
            state="UNKNOWN", severity="UNKNOWN",
            evidence=[f"Only {delivery.shipments} delivered shipments observed."],
            missing_evidence=["sufficient_shipment_history"] + missing,
            provenance=_provenance(result),
            explanation="Supplier risk is UNKNOWN: insufficient shipment observations.",
        )
    late_rate = delivery.late_rate if delivery.late_rate is not None else 0.0
    metrics["late_rate"] = late_rate
    metrics["on_time_rate"] = delivery.on_time_rate
    metrics["average_delay_days"] = delivery.average_delay_days
    metrics["shipments"] = float(delivery.shipments)
    metrics["lead_time_std"] = performance.lead_time_std
    evidence.append(
        f"{delivery.shipments} delivered shipments with late rate {late_rate:.2f}."
    )
    if late_rate >= config.high_delay_rate:
        states.append("HIGH")
        evidence.append("High delivery delay rate.")
    elif late_rate >= config.delayed_rate:
        states.append("MODERATE")
        evidence.append("Recurring delivery delays.")
    else:
        states.append("LOW")
    if (performance.lead_time_std or 0.0) >= config.variable_delay_std:
        states.append("MODERATE")
        evidence.append("High lead-time variability.")
    exposure = result.exposure
    if exposure is not None:
        if exposure.stockout_products:
            states.append("HIGH")
            evidence.append(
                f"Linked to stocked-out products: {sorted(exposure.stockout_products)}."
            )
        elif exposure.at_risk_products:
            states.append("MODERATE")
            evidence.append(
                f"Linked to at-risk products: {sorted(exposure.at_risk_products)}."
            )
        metrics["exposed_products"] = float(len(exposure.affected_products))
    severity = max_severity(states, SUPPLIER_SEVERITY_ORDER)
    return RiskRecord(
        risk_id=risk_id(DOMAIN, "supplier", result.supplier_id, result.analysis_date),
        domain=DOMAIN, entity_type="supplier", entity_id=result.supplier_id,
        supplier_id=result.supplier_id, analysis_date=result.analysis_date,
        state=severity, severity=severity, evidence=evidence, metrics=metrics,
        supporting_records=supporting, missing_evidence=missing,
        confidence={},
        provenance=_provenance(result),
        explanation=(
            f"Supplier risk is {severity} for {result.supplier_name}: "
            + " ".join(evidence[:2])
        ),
    )


def _provenance(result: ProcurementIntelligenceResult) -> dict[str, object]:
    """Carry Phase 6 provenance into the risk record."""
    return {
        "reliability": result.delivery.reliability if result.delivery else None,
        "procurement_signal": result.risk_signal.signal if result.risk_signal else None,
        "data_source": "synthetic",
    }
