"""Transparent hierarchical risk aggregation (Phase 7).

Product/warehouse hierarchy: inventory → supplier exposure → dependency
→ procurement → service → overall exposure. Supplier hierarchy:
supplier risk → exposed products → inventory/service exposure →
supply-chain exposure. Overall states use max-severity plus two
documented combination boosts; every boost names its evidence.
"""

from backend.app.analytics.risk import risk_explanations
from backend.app.analytics.risk.types import (
    RiskRecord,
    max_severity,
    risk_id,
)


def _boosted(severity: str) -> str:
    order = ["UNKNOWN", "LOW", "MODERATE", "HIGH", "CRITICAL"]
    if severity in ("HIGH", "CRITICAL", "UNKNOWN"):
        return severity
    position = order.index(severity)
    return order[min(position + 1, order.index("HIGH"))]


def aggregate_series(
    product_id: str,
    warehouse_id: str,
    analysis_date: str,
    components: list[RiskRecord],
) -> RiskRecord:
    """Aggregate component risks into overall product/warehouse exposure."""
    entity = f"{product_id}|{warehouse_id}"
    by_domain = {record.domain: record for record in components}
    states = [record.severity for record in components
              if record.severity in ("LOW", "MODERATE", "HIGH", "CRITICAL")]
    severity = max_severity(states) if states else "UNKNOWN"
    evidence = [f"{record.domain} risk is {record.severity}." for record in components]
    inventory = by_domain.get("inventory")
    dependency_singles = [
        record for record in components
        if record.domain == "dependency" and record.severity == "HIGH"
    ]
    leadtime = by_domain.get("leadtime")
    if (
        inventory is not None and inventory.severity == "HIGH"
        and dependency_singles
        and leadtime is not None and leadtime.severity in ("HIGH", "MODERATE")
    ):
        severity = _boosted(severity)
        evidence.append(risk_explanations.explain_combination(
            ["HIGH inventory exposure", "SINGLE supplier dependency",
             "HIGH lead-time variability"],
            f"{severity} combined exposure",
        ))
    inbound = by_domain.get("inbound")
    supplier = by_domain.get("supplier") or by_domain.get("procurement")
    if (
        inventory is not None and "projected stockout" in " ".join(
            inventory.evidence or []).lower()
        and inbound is not None and "shortfall" in " ".join(
            inbound.evidence or []).lower()
        and supplier is not None and supplier.severity == "HIGH"
    ):
        severity = _boosted(severity)
        evidence.append(risk_explanations.explain_combination(
            ["PROJECTED STOCKOUT", "NO_KNOWN_INBOUND", "HIGH supplier delay rate"],
            f"{severity} supply exposure",
        ))
    if severity == "UNKNOWN":
        return RiskRecord(
            risk_id=risk_id("overall", "product_warehouse", entity, analysis_date),
            domain="overall", entity_type="product_warehouse", entity_id=entity,
            product_id=product_id, warehouse_id=warehouse_id,
            analysis_date=analysis_date, state="UNKNOWN", severity="UNKNOWN",
            evidence=["No component risk evidence available."],
            missing_evidence=["component_risks"],
            provenance={"data_source": "synthetic"},
            explanation=f"Overall exposure for {entity} is UNKNOWN for lack of evidence.",
        )
    return RiskRecord(
        risk_id=risk_id("overall", "product_warehouse", entity, analysis_date),
        domain="overall", entity_type="product_warehouse", entity_id=entity,
        product_id=product_id, warehouse_id=warehouse_id,
        analysis_date=analysis_date, state=severity, severity=severity,
        evidence=evidence,
        supporting_records=[record.risk_id for record in components],
        provenance={"data_source": "synthetic"},
        explanation=risk_explanations.explain_overall(entity, severity, components),
    )


def aggregate_supplier(
    supplier_id: str,
    analysis_date: str,
    components: list[RiskRecord],
) -> RiskRecord:
    """Aggregate component risks into overall supplier exposure."""
    states = [record.severity for record in components
              if record.severity in ("LOW", "MODERATE", "HIGH", "CRITICAL", "ELEVATED")]
    order = ["UNKNOWN", "LOW", "MODERATE", "ELEVATED", "HIGH", "CRITICAL"]
    known = [state for state in states if state != "UNKNOWN"]
    severity = max(known, key=order.index) if known else "UNKNOWN"
    evidence = [f"{record.domain} risk is {record.severity}." for record in components]
    if severity == "UNKNOWN":
        return RiskRecord(
            risk_id=risk_id("overall", "supplier", supplier_id, analysis_date),
            domain="overall", entity_type="supplier", entity_id=supplier_id,
            supplier_id=supplier_id, analysis_date=analysis_date,
            state="UNKNOWN", severity="UNKNOWN",
            evidence=["No component risk evidence available."],
            missing_evidence=["component_risks"],
            provenance={"data_source": "synthetic"},
            explanation=f"Overall exposure for supplier {supplier_id} is UNKNOWN.",
        )
    return RiskRecord(
        risk_id=risk_id("overall", "supplier", supplier_id, analysis_date),
        domain="overall", entity_type="supplier", entity_id=supplier_id,
        supplier_id=supplier_id, analysis_date=analysis_date,
        state=severity, severity=severity, evidence=evidence,
        supporting_records=[record.risk_id for record in components],
        provenance={"data_source": "synthetic"},
        explanation=risk_explanations.explain_overall(
            f"supplier {supplier_id}", severity, components),
    )
