"""Canonical procurement analytical datasets (Phase 3)."""

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models import PurchaseOrder, PurchaseOrderLine, Shipment, Supplier, SupplierProduct

PO_COLUMNS = [
    "po_id", "po_number", "organization_id", "supplier_id", "supplier_name",
    "product_id", "order_date", "expected_delivery_date", "quantity",
    "unit_cost", "line_total", "moq", "lead_time_days", "status",
]
SHIPMENT_COLUMNS = [
    "shipment_id", "po_id", "supplier_id", "supplier_name", "shipped_date",
    "expected_arrival_date", "actual_arrival_date", "status", "delay_days",
]


async def load_purchase_orders(
    session: AsyncSession,
    start: date | None = None,
    end: date | None = None,
    supplier_ids: list[str] | None = None,
    organization_id: str | None = None,
) -> pd.DataFrame:
    """Load PO lines enriched with supplier terms and names."""
    statement = (
        select(
            PurchaseOrder.id,
            PurchaseOrder.po_number,
            PurchaseOrder.organization_id,
            PurchaseOrder.supplier_id,
            Supplier.name,
            PurchaseOrderLine.product_id,
            PurchaseOrder.order_date,
            PurchaseOrder.expected_delivery_date,
            PurchaseOrderLine.quantity,
            PurchaseOrderLine.unit_cost,
            PurchaseOrderLine.line_total,
            SupplierProduct.min_order_qty,
            SupplierProduct.lead_time_days,
            PurchaseOrder.status,
        )
        .join(PurchaseOrderLine, PurchaseOrderLine.po_id == PurchaseOrder.id)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .join(
            SupplierProduct,
            (SupplierProduct.supplier_id == PurchaseOrder.supplier_id)
            & (SupplierProduct.product_id == PurchaseOrderLine.product_id),
            isouter=True,
        )
    )
    if start is not None:
        statement = statement.where(PurchaseOrder.order_date >= start)
    if end is not None:
        statement = statement.where(PurchaseOrder.order_date <= end)
    if supplier_ids:
        statement = statement.where(PurchaseOrder.supplier_id.in_(supplier_ids))
    if organization_id is not None:
        statement = statement.where(PurchaseOrder.organization_id == organization_id)
    rows = (await session.execute(statement)).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "po_id", "po_number", "organization_id", "supplier_id", "supplier_name",
            "product_id", "order_date", "expected_delivery_date", "quantity",
            "unit_cost", "line_total", "moq", "lead_time_days", "status",
        ],
    )
    if frame.empty:
        return frame.reindex(columns=PO_COLUMNS)
    frame["order_date"] = pd.to_datetime(frame["order_date"]).dt.date
    frame["expected_delivery_date"] = pd.to_datetime(
        frame["expected_delivery_date"]
    ).dt.date
    for column in ("quantity", "unit_cost", "line_total", "moq"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["lead_time_days"] = pd.to_numeric(frame["lead_time_days"], errors="coerce")
    return frame[PO_COLUMNS].sort_values(["order_date", "po_id"]).reset_index(drop=True)


async def load_shipments(
    session: AsyncSession,
    start: date | None = None,
    end: date | None = None,
    supplier_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Load shipments with delay in days (actual − expected)."""
    statement = (
        select(
            Shipment.id,
            Shipment.po_id,
            Shipment.supplier_id,
            Supplier.name,
            Shipment.shipped_date,
            Shipment.expected_arrival_date,
            Shipment.actual_arrival_date,
            Shipment.status,
        ).join(Supplier, Supplier.id == Shipment.supplier_id)
    )
    if start is not None:
        statement = statement.where(Shipment.expected_arrival_date >= start)
    if end is not None:
        statement = statement.where(Shipment.expected_arrival_date <= end)
    if supplier_ids:
        statement = statement.where(Shipment.supplier_id.in_(supplier_ids))
    rows = (await session.execute(statement)).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "shipment_id", "po_id", "supplier_id", "supplier_name", "shipped_date",
            "expected_arrival_date", "actual_arrival_date", "status",
        ],
    )
    if frame.empty:
        empty = frame.reindex(columns=SHIPMENT_COLUMNS)
        return empty
    for column in ("shipped_date", "expected_arrival_date", "actual_arrival_date"):
        frame[column] = pd.to_datetime(frame[column]).dt.date
    frame["delay_days"] = (
        pd.to_datetime(frame["actual_arrival_date"]) - pd.to_datetime(frame["expected_arrival_date"])
    ).dt.days.astype("float")
    return frame[SHIPMENT_COLUMNS].sort_values(
        ["expected_arrival_date", "shipment_id"]
    ).reset_index(drop=True)
