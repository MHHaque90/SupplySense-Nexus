"""Procurement risk domain (Phase 7).

Consumes Phase 6 open-order, inbound, MOQ, and delay evidence per
supplier. States mirror the procurement vocabulary
(NO_SIGNAL/MONITOR/ELEVATED/HIGH_EXPOSURE/UNKNOWN).
"""

from backend.app.analytics.procurement.types import ProcurementIntelligenceResult
from backend.app.analytics.risk.types import (
    PROCUREMENT_SEVERITY_ORDER,
    RiskIntelligenceConfig,
    RiskRecord,
    max_severity,
    risk_id,
)

DOMAIN = "procurement"


def assess(
    result: ProcurementIntelligenceResult,
    config: RiskIntelligenceConfig,
) -> RiskRecord:
    """Assess procurement risk for one supplier result."""
    del config
    evidence: list[str] = []
    metrics: dict[str, float | None] = {}
    # Missing evidence is derived from structured absences, never copied
    # from upstream warning prose.
    missing: list[str] = []
    states: list[str] = []
    overdue = [order for order in result.open_orders if order.overdue]
    remaining = sum(order.remaining_quantity for order in result.open_orders)
    metrics["open_lines"] = float(len(result.open_orders))
    metrics["overdue_lines"] = float(len(overdue))
    metrics["remaining_quantity"] = remaining
    if not result.open_orders:
        missing.append("open_orders")
    if overdue:
        states.append("ELEVATED")
        evidence.append(f"{len(overdue)} overdue open order line(s).")
    delayed = sum(
        1 for rel in result.relationships
        if (rel.observed_lead_time_days or 0) > 0 and (rel.on_time_rate or 1.0) < 1.0
    )
    if delayed:
        states.append("MONITOR")
        evidence.append(f"{delayed} relationship(s) show historical delays.")
    moq_rates = [
        row.compliance_rate for row in result.moq
        if row.compliance_rate is not None
    ]
    if moq_rates:
        worst = min(moq_rates)
        metrics["worst_moq_compliance"] = worst
        if worst < 1.0:
            states.append("MONITOR")
            evidence.append(f"Lowest MOQ compliance is {worst:.2f}.")
    else:
        missing.append("moq_terms")
    if not states:
        if result.open_orders:
            states.append("NO_SIGNAL")
            evidence.append("Open commitments exist with no overdue or delay evidence.")
        else:
            return RiskRecord(
                risk_id=risk_id(DOMAIN, "supplier", result.supplier_id, result.analysis_date),
                domain=DOMAIN, entity_type="supplier", entity_id=result.supplier_id,
                supplier_id=result.supplier_id, analysis_date=result.analysis_date,
                state="UNKNOWN", severity="UNKNOWN",
                evidence=["No open procurement evidence available."],
                missing_evidence=["open_procurement"] + missing,
                provenance=_provenance(result),
                explanation="Procurement risk is UNKNOWN for lack of open-order evidence.",
            )
    severity = max_severity(states, PROCUREMENT_SEVERITY_ORDER)
    return RiskRecord(
        risk_id=risk_id(DOMAIN, "supplier", result.supplier_id, result.analysis_date),
        domain=DOMAIN, entity_type="supplier", entity_id=result.supplier_id,
        supplier_id=result.supplier_id, analysis_date=result.analysis_date,
        state=severity, severity=severity, evidence=evidence, metrics=metrics,
        supporting_records=[f"phase6:{result.supplier_id}:{result.analysis_date}"],
        missing_evidence=missing,
        confidence={},
        provenance=_provenance(result),
        explanation=(
            f"Procurement risk is {severity} for {result.supplier_name}: "
            + " ".join(evidence[:2])
        ),
    )


def _provenance(result: ProcurementIntelligenceResult) -> dict[str, object]:
    """Carry Phase 6 provenance into the risk record."""
    return {
        "procurement_signal": result.risk_signal.signal if result.risk_signal else None,
        "data_source": "synthetic",
    }
