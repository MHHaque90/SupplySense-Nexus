"""Inventory movement features (Phase 3)."""

import pandas as pd

_SIGNED_TYPES = {
    "OPENING_BALANCE": 1.0,
    "RECEIPT": 1.0,
    "TRANSFER_IN": 1.0,
    "RETURN": 1.0,
    "ADJUSTMENT": 1.0,
    "SALE": -1.0,
    "TRANSFER_OUT": -1.0,
}


def signed_quantities(frame: pd.DataFrame) -> pd.DataFrame:
    """Attach a signed quantity column (inflows positive, outflows negative)."""
    work = frame.copy()
    work["signed_quantity"] = work.apply(
        lambda row: float(row["quantity"]) * _SIGNED_TYPES.get(str(row["transaction_type"]), 0.0),
        axis=1,
    )
    return work


def daily_movement(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate signed movements per product/warehouse/day."""
    work = signed_quantities(frame)
    work["timestamp"] = pd.to_datetime(work["timestamp"]).dt.date
    inflows = work[work["signed_quantity"] > 0].groupby(
        ["product_id", "warehouse_id", "timestamp"], as_index=False
    )["signed_quantity"].sum().rename(columns={"signed_quantity": "inflow"})
    outflows = work[work["signed_quantity"] < 0].groupby(
        ["product_id", "warehouse_id", "timestamp"], as_index=False
    )["signed_quantity"].sum().rename(columns={"signed_quantity": "outflow"})
    merged = inflows.merge(outflows, on=["product_id", "warehouse_id", "timestamp"], how="outer").fillna(0.0)
    merged["outflow"] = -merged["outflow"]
    merged["net"] = merged["inflow"] - merged["outflow"]
    return merged.sort_values(["product_id", "warehouse_id", "timestamp"]).reset_index(drop=True)
