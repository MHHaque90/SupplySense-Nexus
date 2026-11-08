"""Procurement/service co-occurrence (Phase 6, no causality).

Reports when supplier delivery delays occur during periods containing
inventory service exposure. Never claims a supplier caused a stockout.
"""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.procurement.types import ServiceExposure


def describe_cooccurrence(
    supplier_id: str,
    shipments: pd.DataFrame,
    intelligence: list[InventoryIntelligenceResult],
    analysis_date: date,
    recent_window_days: int = 90,
) -> list[ServiceExposure]:
    """Link delayed shipments to service-exposed series without causality."""
    cutoff = analysis_date.fromordinal(analysis_date.toordinal() - recent_window_days)
    delayed = shipments[
        (shipments["supplier_id"] == supplier_id)
        & (shipments["actual_arrival_date"].notna())
        & (pd.to_datetime(shipments["actual_arrival_date"]).dt.date <= analysis_date)
        & (pd.to_datetime(shipments["actual_arrival_date"]).dt.date >= cutoff)
        & (shipments["delay_days"].astype(float) > 0)
    ]
    if delayed.empty:
        return []
    delayed_pos = set(delayed["po_id"].astype(str).unique())
    results: list[ServiceExposure] = []
    for result in intelligence:
        flag = ""
        if result.health and result.health.health in ("AT_RISK", "CRITICAL", "STOCKOUT"):
            flag = result.health.health
        elif result.stockout and result.stockout.exposure in ("elevated", "watch"):
            flag = f"exposure:{result.stockout.exposure}"
        if not flag:
            continue
        results.append(ServiceExposure(
            supplier_id=supplier_id,
            product_id=result.product_id,
            warehouse_id=result.warehouse_id,
            delayed_shipments=len(delayed_pos),
            service_flag=flag,
            description=(
                f"The product experienced {len(delayed_pos)} delayed supplier "
                f"shipment(s) during a period containing inventory service "
                f"exposure ({flag}). Association only; no causality is claimed."
            ),
        ))
    return results
