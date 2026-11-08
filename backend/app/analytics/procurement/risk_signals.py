"""Descriptive procurement risk signals (Phase 6).

Rule-based categories with evidence — never an aggregate score, never
a ranking. Signal ladder: UNKNOWN (insufficient evidence) < NO_SIGNAL
< MONITOR < ELEVATED < HIGH_EXPOSURE.
"""

from backend.app.analytics.procurement.types import (
    DeliveryMetrics,
    OpenOrderMetrics,
    ProcurementIntelligenceConfig,
    ProcurementRiskSignal,
    SupplierExposure,
)


def supplier_risk_signal(
    supplier_id: str,
    delivery: DeliveryMetrics | None,
    exposure: SupplierExposure | None,
    open_orders: list[OpenOrderMetrics],
    single_supplier_products: list[str],
    concentrated: bool,
    high_uncertainty_products: list[str],
    config: ProcurementIntelligenceConfig,
) -> ProcurementRiskSignal:
    """Combine evidence flags into a descriptive supplier risk signal."""
    signal = ProcurementRiskSignal(supplier_id=supplier_id, severity="unknown")
    evidence: list[str] = []
    missing: list[str] = []
    metrics: dict[str, float | None] = {}
    level = 0  # 0 unknown, 1 no_signal, 2 monitor, 3 elevated, 4 high_exposure

    if delivery is None or delivery.reliability == "UNKNOWN":
        missing.append("delivery_history")
    else:
        metrics["late_rate"] = delivery.late_rate
        metrics["shipments"] = float(delivery.shipments)
        if delivery.reliability == "HIGH_DELAY":
            evidence.append(f"High delivery delays: late rate {delivery.late_rate:.2f}.")
            level = max(level, 3)
        elif delivery.reliability == "DELAYED":
            evidence.append(f"Recurring delivery delays: late rate {delivery.late_rate:.2f}.")
            level = max(level, 2)
        elif delivery.reliability == "VARIABLE":
            evidence.append("Variable delivery timing across observed shipments.")
            level = max(level, 2)

    overdue = [order for order in open_orders if order.overdue and order.remaining_quantity > 0]
    if overdue:
        evidence.append(f"{len(overdue)} overdue open order line(s) with remaining quantity.")
        level = max(level, 3)
        metrics["overdue_lines"] = float(len(overdue))
    elif open_orders:
        level = max(level, 1)

    if exposure is not None:
        metrics["at_risk_products"] = float(len(exposure.at_risk_products))
        metrics["stockout_products"] = float(len(exposure.stockout_products))
        metrics["urgent_products"] = float(len(exposure.urgent_products))
        if exposure.stockout_products:
            evidence.append(
                f"Linked to stocked-out products: {sorted(exposure.stockout_products)}."
            )
            level = max(level, 4)
        elif exposure.at_risk_products:
            evidence.append(
                f"Linked to at-risk products: {sorted(exposure.at_risk_products)}."
            )
            level = max(level, 3)
        elif exposure.affected_products:
            level = max(level, 1)
        if exposure.urgent_products:
            evidence.append(
                f"Linked to urgent reorder signals: {sorted(exposure.urgent_products)}."
            )
            level = max(level, 3)
    else:
        missing.append("inventory_exposure")

    if single_supplier_products:
        evidence.append(
            f"Single-supplier dependency for products: {sorted(single_supplier_products)}."
        )
        level = max(level, 2)
    if concentrated:
        evidence.append("High procurement concentration share for this supplier.")
        level = max(level, 2)
    if high_uncertainty_products:
        evidence.append(
            f"High forecast uncertainty on linked products: {sorted(high_uncertainty_products)}."
        )
        level = max(level, 2)

    names = {0: "UNKNOWN", 1: "NO_SIGNAL", 2: "MONITOR", 3: "ELEVATED", 4: "HIGH_EXPOSURE"}
    signal.signal = names[level]
    signal.severity = names[level].lower()
    if level == 0:
        signal.reason = "Insufficient evidence to assess procurement risk."
    elif level == 1:
        signal.reason = "No elevated procurement risk signals in observed evidence."
    else:
        signal.reason = (
            f"{names[level].title()} procurement risk: "
            + " ".join(evidence[:2])
            + " Descriptive only; no procurement action is recommended."
        )
    signal.evidence = evidence
    signal.metrics = metrics
    signal.missing_evidence = missing
    _ = config
    return signal
