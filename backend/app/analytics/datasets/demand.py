"""Canonical demand analytical dataset (Phase 3)."""

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import DemandObservation, Product, ProductCategory, Warehouse

DEMAND_COLUMNS = [
    "date",
    "organization_id",
    "product_id",
    "warehouse_id",
    "quantity",
    "sku",
    "product_name",
    "category",
    "warehouse_name",
]


async def load_demand(
    session: AsyncSession,
    start: date | None = None,
    end: date | None = None,
    product_ids: list[str] | None = None,
    warehouse_ids: list[str] | None = None,
    organization_id: str | None = None,
) -> pd.DataFrame:
    """Load the canonical demand frame, one row per product/warehouse/day.

    Missing calendar days are NOT imputed here: continuity handling is an
    explicit, documented step in feature engineering.
    """
    statement = (
        select(
            DemandObservation.date,
            Product.organization_id,
            DemandObservation.product_id,
            DemandObservation.warehouse_id,
            DemandObservation.quantity,
            Product.sku,
            Product.name,
            ProductCategory.name,
            Warehouse.name,
        )
        .join(Product, Product.id == DemandObservation.product_id)
        .join(Warehouse, Warehouse.id == DemandObservation.warehouse_id)
        .join(ProductCategory, ProductCategory.id == Product.category_id, isouter=True)
    )
    if start is not None:
        statement = statement.where(DemandObservation.date >= start)
    if end is not None:
        statement = statement.where(DemandObservation.date <= end)
    if product_ids:
        statement = statement.where(DemandObservation.product_id.in_(product_ids))
    if warehouse_ids:
        statement = statement.where(DemandObservation.warehouse_id.in_(warehouse_ids))
    if organization_id is not None:
        statement = statement.where(Product.organization_id == organization_id)
    rows = (await session.execute(statement)).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "date", "organization_id", "product_id", "warehouse_id", "quantity",
            "sku", "product_name", "category", "warehouse_name",
        ],
    )
    if frame.empty:
        return frame.reindex(columns=DEMAND_COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame["quantity"] = frame["quantity"].astype(float)
    return frame[DEMAND_COLUMNS].sort_values(["product_id", "warehouse_id", "date"]).reset_index(drop=True)


def aggregate_demand(frame: pd.DataFrame, grain: str = "day", by: tuple[str, ...] = ("product_id", "warehouse_id")) -> pd.DataFrame:
    """Aggregate demand deterministically to day/week/month grains.

    Args:
        frame: Canonical demand frame.
        grain: One of ``day``, ``week`` (ISO week starting Monday), ``month``.
        by: Dimension columns preserved alongside the period.
    """
    if frame.empty:
        return frame.copy()
    if grain not in ("day", "week", "month"):
        raise ValueError(f"Unsupported grain: {grain}")
    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"])
    if grain == "day":
        work["period"] = work["date"].dt.date
    elif grain == "week":
        work["period"] = (work["date"] - pd.to_timedelta(work["date"].dt.weekday, unit="D")).dt.date
    else:
        work["period"] = work["date"].dt.to_period("M").dt.to_timestamp().dt.date
    grouped = work.groupby(["period", *by], as_index=False)["quantity"].sum()
    return grouped.sort_values(["period", *by]).reset_index(drop=True)
