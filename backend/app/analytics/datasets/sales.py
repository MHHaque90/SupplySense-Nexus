"""Canonical sales analytical datasets (Phase 3)."""

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import SalesOrder, SalesOrderLine

ORDER_COLUMNS = [
    "order_id", "customer_id", "order_date", "warehouse_id",
    "total_amount", "status", "organization_id",
]
LINE_COLUMNS = [
    "order_id", "order_date", "warehouse_id", "status", "organization_id",
    "product_id", "quantity", "unit_price",
]


async def load_sales_orders(
    session: AsyncSession,
    start: date | None = None,
    end: date | None = None,
    warehouse_ids: list[str] | None = None,
    organization_id: str | None = None,
) -> pd.DataFrame:
    """Load sales order headers."""
    statement = select(
        SalesOrder.id,
        SalesOrder.customer_id,
        SalesOrder.order_date,
        SalesOrder.warehouse_id,
        SalesOrder.total_amount,
        SalesOrder.status,
        SalesOrder.organization_id,
    )
    if start is not None:
        statement = statement.where(SalesOrder.order_date >= start)
    if end is not None:
        statement = statement.where(SalesOrder.order_date <= end)
    if warehouse_ids:
        statement = statement.where(SalesOrder.warehouse_id.in_(warehouse_ids))
    if organization_id is not None:
        statement = statement.where(SalesOrder.organization_id == organization_id)
    rows = (await session.execute(statement)).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "order_id", "customer_id", "order_date", "warehouse_id",
            "total_amount", "status", "organization_id",
        ],
    )
    if frame.empty:
        return frame.reindex(columns=ORDER_COLUMNS)
    frame["order_date"] = pd.to_datetime(frame["order_date"]).dt.date
    return frame[ORDER_COLUMNS].sort_values(["order_date", "order_id"]).reset_index(drop=True)


async def load_sales_lines(
    session: AsyncSession,
    start: date | None = None,
    end: date | None = None,
    product_ids: list[str] | None = None,
    warehouse_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Load sales lines enriched with order date/warehouse/status."""
    statement = (
        select(
            SalesOrderLine.sales_order_id,
            SalesOrder.order_date,
            SalesOrder.warehouse_id,
            SalesOrder.status,
            SalesOrder.organization_id,
            SalesOrderLine.product_id,
            SalesOrderLine.quantity,
            SalesOrderLine.unit_price,
        ).join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
    )
    if start is not None:
        statement = statement.where(SalesOrder.order_date >= start)
    if end is not None:
        statement = statement.where(SalesOrder.order_date <= end)
    if product_ids:
        statement = statement.where(SalesOrderLine.product_id.in_(product_ids))
    if warehouse_ids:
        statement = statement.where(SalesOrder.warehouse_id.in_(warehouse_ids))
    rows = (await session.execute(statement)).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "order_id", "order_date", "warehouse_id", "status", "organization_id",
            "product_id", "quantity", "unit_price",
        ],
    )
    if frame.empty:
        return frame.reindex(columns=LINE_COLUMNS)
    frame["order_date"] = pd.to_datetime(frame["order_date"]).dt.date
    frame["quantity"] = frame["quantity"].astype(float)
    return frame[LINE_COLUMNS].sort_values(
        ["order_date", "order_id", "product_id"]
    ).reset_index(drop=True)
