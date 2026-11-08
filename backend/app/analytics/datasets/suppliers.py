"""Canonical supplier analytical dataset (Phase 3, descriptive only)."""

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import Product, Supplier, SupplierProduct

SUPPLIER_COLUMNS = [
    "supplier_id", "supplier_name", "country", "rating", "organization_id",
    "product_id", "sku", "unit_cost", "lead_time_days", "min_order_qty",
    "capacity_units",
]


async def load_suppliers(
    session: AsyncSession,
    supplier_ids: list[str] | None = None,
    organization_id: str | None = None,
) -> pd.DataFrame:
    """Load suppliers with their product links (one row per link).

    Suppliers without product links are excluded; link-less suppliers
    carry no analytical terms to describe.
    """
    statement = (
        select(
            Supplier.id,
            Supplier.name,
            Supplier.country,
            Supplier.rating,
            Supplier.organization_id,
            SupplierProduct.product_id,
            Product.sku,
            SupplierProduct.unit_cost,
            SupplierProduct.lead_time_days,
            SupplierProduct.min_order_qty,
            SupplierProduct.capacity_units,
        )
        .join(SupplierProduct, SupplierProduct.supplier_id == Supplier.id)
        .join(Product, Product.id == SupplierProduct.product_id)
    )
    if supplier_ids:
        statement = statement.where(Supplier.id.in_(supplier_ids))
    if organization_id is not None:
        statement = statement.where(Supplier.organization_id == organization_id)
    rows = (await session.execute(statement)).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "supplier_id", "supplier_name", "country", "rating", "organization_id",
            "product_id", "sku", "unit_cost", "lead_time_days", "min_order_qty",
            "capacity_units",
        ],
    )
    if frame.empty:
        return frame.reindex(columns=SUPPLIER_COLUMNS)
    frame["rating"] = pd.to_numeric(frame["rating"], errors="coerce")
    frame["unit_cost"] = pd.to_numeric(frame["unit_cost"], errors="coerce")
    frame["min_order_qty"] = pd.to_numeric(frame["min_order_qty"], errors="coerce")
    frame["capacity_units"] = pd.to_numeric(frame["capacity_units"], errors="coerce")
    return frame[SUPPLIER_COLUMNS].sort_values(
        ["supplier_id", "product_id"]
    ).reset_index(drop=True)
