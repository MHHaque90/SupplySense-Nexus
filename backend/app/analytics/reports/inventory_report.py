"""Inventory report section (Phase 3)."""

from typing import Any

import pandas as pd

from backend.app.analytics.kpis import inventory_kpis
from backend.app.analytics.types import KPIResult


def inventory_section(
    snapshots: pd.DataFrame,
    transactions: pd.DataFrame,
    average_daily_demand: float | None = None,
) -> dict[str, Any]:
    """Build the inventory section from analytical frames."""
    kpis: list[KPIResult] = []
    kpis.extend(inventory_kpis.inventory_levels(snapshots))
    kpis.extend(inventory_kpis.stockout_stats(snapshots))
    kpis.extend(inventory_kpis.turnover_proxy(transactions, snapshots))
    kpis.extend(inventory_kpis.movement_summary(transactions))
    kpis.extend(inventory_kpis.reconciliation_status(transactions, snapshots))
    if average_daily_demand is not None:
        kpis.extend(inventory_kpis.days_of_supply(snapshots, average_daily_demand))
    latest = []
    if not snapshots.empty:
        ordered = snapshots.sort_values("snapshot_date").groupby(
            ["product_id", "warehouse_id"], as_index=False).tail(1)
        latest = [
            {"product_id": str(r["product_id"]), "warehouse_id": str(r["warehouse_id"]),
             "on_hand": float(r["on_hand"]), "snapshot_date": str(r["snapshot_date"])}
            for _, r in ordered.iterrows()
        ]
    return {
        "kpis": [kpi.to_dict() for kpi in kpis],
        "current_positions": latest,
    }
