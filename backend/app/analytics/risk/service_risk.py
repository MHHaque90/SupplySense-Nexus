"""Service risk domain (Phase 7).

Consumes Phase 5 service signals and Phase 6 delay/service
associations with association-only language. Never claims a supplier
caused a service failure.
"""

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.procurement.types import ServiceExposure
from backend.app.analytics.risk.types import (
    RiskIntelligenceConfig,
    RiskRecord,
    max_severity,
    risk_id,
)

DOMAIN = "service"


def assess(
    result: InventoryIntelligenceResult,
    cooccurrences: list[ServiceExposure],
    config: RiskIntelligenceConfig,
) -> RiskRecord:
    """Assess service risk for one product/warehouse result."""
    del config
    entity = f"{result.product_id}|{result.warehouse_id}"
    evidence: list[str] = []
    missing: list[str] = []
    metrics: dict[str, float | None] = {}
    states: list[str] = []
    stockouts = result.position.stockout_observations if result.position else 0
    metrics["stockout_observations"] = float(stockouts)
    if result.position is None or result.position.unknown:
        return RiskRecord(
            risk_id=risk_id(DOMAIN, "product_warehouse", entity, result.analysis_date),
            domain=DOMAIN, entity_type="product_warehouse", entity_id=entity,
            product_id=result.product_id, warehouse_id=result.warehouse_id,
            analysis_date=result.analysis_date, state="UNKNOWN", severity="UNKNOWN",
            evidence=["No snapshot history for service assessment."],
            missing_evidence=["service_history"],
            provenance={"data_source": "synthetic"},
            explanation="Service risk is UNKNOWN for lack of service history.",
        )
    if stockouts >= 2:
        states.append("HIGH")
        evidence.append(f"{stockouts} historical stockout observations.")
    elif stockouts == 1:
        states.append("MODERATE")
        evidence.append("One historical stockout observation.")
    service_note = (result.service_note or "").lower()
    # Match affirmed warnings only; negated text ("no repeated ...")
    # must not trigger.
    if "repeated recent stockouts" in service_note and "no repeated" not in service_note:
        states.append("MODERATE")
        evidence.append("Service evidence flags repeated recent stockouts.")
    own = [item for item in cooccurrences if item.product_id == result.product_id
           and item.warehouse_id == result.warehouse_id]
    metrics["delay_associations"] = float(len(own))
    for item in own:
        evidence.append(
            f"Supplier {item.supplier_id} had delivery delays during a period "
            f"containing service exposure ({item.service_flag})."
        )
        states.append("MODERATE")
    if not states:
        if result.position is None or result.position.unknown:
            return RiskRecord(
                risk_id=risk_id(DOMAIN, "product_warehouse", entity, result.analysis_date),
                domain=DOMAIN, entity_type="product_warehouse", entity_id=entity,
                product_id=result.product_id, warehouse_id=result.warehouse_id,
                analysis_date=result.analysis_date, state="UNKNOWN", severity="UNKNOWN",
                evidence=["No service history available."],
                missing_evidence=["service_history"],
                provenance={"data_source": "synthetic"},
                explanation="Service risk is UNKNOWN for lack of service history.",
            )
        states.append("LOW")
        evidence.append("No repeated stockouts or delay associations observed.")
    severity = max_severity(states)
    return RiskRecord(
        risk_id=risk_id(DOMAIN, "product_warehouse", entity, result.analysis_date),
        domain=DOMAIN, entity_type="product_warehouse", entity_id=entity,
        product_id=result.product_id, warehouse_id=result.warehouse_id,
        analysis_date=result.analysis_date, state=severity, severity=severity,
        evidence=evidence, metrics=metrics,
        supporting_records=[f"phase5:{entity}:{result.analysis_date}"],
        missing_evidence=missing,
        provenance={"data_source": "synthetic"},
        explanation=f"Service risk is {severity} for {entity}: " + " ".join(evidence[:2]),
    )
