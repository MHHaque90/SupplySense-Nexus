"""Delivery intelligence with descriptive reliability classes (Phase 6).

Classes are evidence-based categories, never rankings:
- UNKNOWN: fewer delivered shipments than the configured minimum.
- STABLE: sufficient history with no late arrivals beyond grace.
- HIGH_DELAY: late rate above the high-delay cutoff.
- DELAYED: late rate above the delayed cutoff.
- VARIABLE: otherwise, when delay spread exceeds the variability cutoff;
  remaining cases with modest delays are DELAYED-adjacent MONITOR-free
  VARIABLE only by spread, else DELAYED when any lateness exists.

Rule order is fixed and documented; every outcome carries evidence.
"""

from datetime import date

import pandas as pd

from backend.app.analytics.procurement.types import (
    DeliveryMetrics,
    ProcurementIntelligenceConfig,
)


def describe_delivery(
    supplier_id: str,
    shipments: pd.DataFrame,
    analysis_date: date,
    config: ProcurementIntelligenceConfig,
) -> DeliveryMetrics:
    """Classify delivery reliability for one supplier at a date."""
    delivered = shipments[
        (shipments["supplier_id"] == supplier_id)
        & (shipments["actual_arrival_date"].notna())
        & (pd.to_datetime(shipments["actual_arrival_date"]).dt.date <= analysis_date)
    ]
    total = len(delivered)
    if total < config.min_shipments:
        return DeliveryMetrics(
            supplier_id=supplier_id,
            reliability="UNKNOWN",
            shipments=total,
            evidence=f"Only {total} delivered shipments; minimum is {config.min_shipments}.",
            missing_evidence=["delivered_shipment_history"],
        )
    delays = delivered["delay_days"].astype(float)
    late = int((delays > config.late_grace_days).sum())
    on_time = total - late
    late_rate = late / total
    std = float(delays.std(ddof=0)) if total > 1 else 0.0
    if late == 0:
        reliability = "STABLE"
        evidence = f"{total} delivered shipments with no late arrivals beyond grace."
    elif late_rate >= config.high_delay_rate:
        reliability = "HIGH_DELAY"
        evidence = f"Late rate {late_rate:.2f} meets the high-delay cutoff."
    elif late_rate >= config.delayed_rate:
        reliability = "DELAYED"
        evidence = f"Late rate {late_rate:.2f} meets the delayed cutoff."
    elif std >= config.variable_delay_std:
        reliability = "VARIABLE"
        evidence = f"Delay spread {std:.1f} days meets the variability cutoff."
    else:
        reliability = "DELAYED"
        evidence = f"Late rate {late_rate:.2f} with modest spread; classified DELAYED."
    return DeliveryMetrics(
        supplier_id=supplier_id,
        reliability=reliability,
        shipments=total,
        on_time=on_time,
        late=late,
        on_time_rate=on_time / total,
        late_rate=late_rate,
        average_delay_days=float(delays.mean()),
        delay_std=std,
        evidence=evidence,
    )
