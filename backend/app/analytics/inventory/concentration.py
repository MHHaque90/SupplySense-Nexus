"""Descriptive inventory concentration (Phase 5).

Reports where inventory units sit; never recommends transfers or
allocation changes.
"""

import pandas as pd


def concentration_by_warehouse(snapshots: pd.DataFrame) -> list[dict[str, object]]:
    """Share of latest on-hand units held per warehouse."""
    if snapshots.empty:
        return []
    latest = snapshots.sort_values("snapshot_date").groupby(
        ["product_id", "warehouse_id"], as_index=False).tail(1)
    totals = latest.groupby("warehouse_id")["on_hand"].sum()
    grand = float(totals.sum())
    return [
        {"warehouse_id": str(warehouse), "units": float(units),
         "share": (float(units) / grand) if grand else None}
        for warehouse, units in totals.items()
    ]


def concentration_by_product(snapshots: pd.DataFrame, top_n: int = 5) -> list[dict[str, object]]:
    """Top-N products by latest on-hand units with shares."""
    if snapshots.empty:
        return []
    latest = snapshots.sort_values("snapshot_date").groupby(
        ["product_id", "warehouse_id"], as_index=False).tail(1)
    totals = latest.groupby("product_id")["on_hand"].sum().sort_values(ascending=False)
    grand = float(totals.sum())
    return [
        {"product_id": str(product), "units": float(units),
         "share": (float(units) / grand) if grand else None}
        for product, units in totals.head(max(1, top_n)).items()
    ]
