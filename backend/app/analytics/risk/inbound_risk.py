"""Inbound exposure risk domain (Phase 7).

Consumes Phase 6 inbound coverage states and connects them with
projected stockout, DOS, health, and supplier dependency evidence.
Never recommends expediting or cancelling purchase orders.
"""

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.procurement.types import InboundCoverage
from backend.app.analytics.risk.types import (
    RiskIntelligenceConfig,
    RiskRecord,
    max_severity,
    risk_id,
)

DOMAIN = "inbound"


def assess(
    result: InventoryIntelligenceResult,
    coverage: InboundCoverage | None,
    config: RiskIntelligenceConfig,
) -> RiskRecord:
    """Assess inbound exposure risk for one product/warehouse result."""
    del config
    entity = f"{result.product_id}|{result.warehouse_id}"
    if coverage is None or coverage.state == "UNKNOWN":
        return RiskRecord(
            risk_id=risk_id(DOMAIN, "product_warehouse", entity, result.analysis_date),
            domain=DOMAIN, entity_type="product_warehouse", entity_id=entity,
            product_id=result.product_id, warehouse_id=result.warehouse_id,
            analysis_date=result.analysis_date, state="UNKNOWN", severity="UNKNOWN",
            evidence=["Inbound coverage is unknown."],
            missing_evidence=["inbound_coverage"],
            provenance={"data_source": "synthetic"},
            explanation="Inbound risk is UNKNOWN without coverage evidence.",
        )
    states: list[str] = []
    evidence = [f"Inbound coverage state is {coverage.state}."]
    if coverage.state == "INBOUND_SUPPORTED":
        states.append("LOW")
    elif coverage.state == "INBOUND_PARTIAL":
        states.append("MODERATE")
        evidence.append("Known inbound covers only part of the shortfall.")
    elif coverage.state in ("INBOUND_INSUFFICIENT", "NO_KNOWN_INBOUND"):
        states.append("HIGH")
        evidence.append(
            f"Uncovered demand is {coverage.uncovered_demand} with "
            f"known inbound {coverage.known_inbound}."
        )
    stockout = result.stockout.exposure if result.stockout else "unknown"
    if stockout in ("immediate", "elevated") and states and states[0] != "LOW":
        evidence.append(f"Projected stockout exposure is {stockout}.")
    severity = max_severity(states) if states else "LOW"
    return RiskRecord(
        risk_id=risk_id(DOMAIN, "product_warehouse", entity, result.analysis_date),
        domain=DOMAIN, entity_type="product_warehouse", entity_id=entity,
        product_id=result.product_id, warehouse_id=result.warehouse_id,
        analysis_date=result.analysis_date, state=severity, severity=severity,
        evidence=evidence,
        metrics={"known_inbound": coverage.known_inbound,
                 "uncovered_demand": coverage.uncovered_demand},
        supporting_records=[f"phase5:{entity}:{result.analysis_date}"],
        provenance={"data_source": "synthetic"},
        explanation=f"Inbound exposure risk is {severity} for {entity}.",
    )
