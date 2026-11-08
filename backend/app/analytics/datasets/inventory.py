"""Canonical inventory analytical datasets (Phase 3)."""

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import InventorySnapshot, InventoryTransaction, Product

SNAPSHOT_COLUMNS = [
    "snapshot_date", "organization_id", "product_id", "warehouse_id",
    "on_hand", "reserved", "in_transit", "sku", "unit_cost",
]
TRANSACTION_COLUMNS = [
    "timestamp", "organization_id", "product_id", "warehouse_id",
    "transaction_type", "quantity",
]


async def load_snapshots(
    session: AsyncSession,
    start: date | None = None,
    end: date | None = None,
    product_ids: list[str] | None = None,
    warehouse_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Load inventory snapshots with unit-cost basis where available.

    Inventory value is computable only when the product carries a
    unit cost; rows without one keep ``unit_cost`` null and downstream
    metrics stay quantity-based (documented limitation).
    """
    statement = (
        select(
            InventorySnapshot.snapshot_date,
            Product.organization_id,
            InventorySnapshot.product_id,
            InventorySnapshot.warehouse_id,
            InventorySnapshot.available_qty,
            InventorySnapshot.reserved_qty,
            InventorySnapshot.in_transit_qty,
            Product.sku,
            Product.unit_cost,
        )
        .join(Product, Product.id == InventorySnapshot.product_id)
    )
    if start is not None:
        statement = statement.where(InventorySnapshot.snapshot_date >= start)
    if end is not None:
        statement = statement.where(InventorySnapshot.snapshot_date <= end)
    if product_ids:
        statement = statement.where(InventorySnapshot.product_id.in_(product_ids))
    if warehouse_ids:
        statement = statement.where(InventorySnapshot.warehouse_id.in_(warehouse_ids))
    rows = (await session.execute(statement)).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "snapshot_date", "organization_id", "product_id", "warehouse_id",
            "on_hand", "reserved", "in_transit", "sku", "unit_cost",
        ],
    )
    if frame.empty:
        return frame.reindex(columns=SNAPSHOT_COLUMNS)
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"]).dt.date
    for column in ("on_hand", "reserved", "in_transit"):
        frame[column] = frame[column].astype(float)
    frame["unit_cost"] = pd.to_numeric(frame["unit_cost"], errors="coerce")
    return frame[SNAPSHOT_COLUMNS].sort_values(
        ["product_id", "warehouse_id", "snapshot_date"]
    ).reset_index(drop=True)


async def load_transactions(
    session: AsyncSession,
    start: date | None = None,
    end: date | None = None,
    product_ids: list[str] | None = None,
    warehouse_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Load inventory movements with signed quantities resolved downstream."""
    statement = (
        select(
            InventoryTransaction.timestamp,
            Product.organization_id,
            InventoryTransaction.product_id,
            InventoryTransaction.warehouse_id,
            InventoryTransaction.transaction_type,
            InventoryTransaction.quantity,
        ).join(Product, Product.id == InventoryTransaction.product_id)
    )
    if start is not None:
        statement = statement.where(InventoryTransaction.timestamp >= start)
    if end is not None:
        statement = statement.where(InventoryTransaction.timestamp <= end)
    if product_ids:
        statement = statement.where(InventoryTransaction.product_id.in_(product_ids))
    if warehouse_ids:
        statement = statement.where(InventoryTransaction.warehouse_id.in_(warehouse_ids))
    rows = (await session.execute(statement)).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "timestamp", "organization_id", "product_id", "warehouse_id",
            "transaction_type", "quantity",
        ],
    )
    if frame.empty:
        return frame.reindex(columns=TRANSACTION_COLUMNS)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"]).dt.date
    frame["quantity"] = frame["quantity"].astype(float)
    return frame[TRANSACTION_COLUMNS].sort_values(
        ["product_id", "warehouse_id", "timestamp"]
    ).reset_index(drop=True)
