"""Service-level KPIs (Phase 3).

Denominators are explicit per metric. Order-status fill rates are a
proxy: the schema records requested line quantities but no fulfilled
quantities, so line-level fill uses order status as documented.
"""

import pandas as pd

from backend.app.analytics.types import KPIResult


def order_fulfillment_rate(sales_orders: pd.DataFrame, sales_lines: pd.DataFrame) -> list[KPIResult]:
    """Share of sales orders fully fulfilled (status-based proxy)."""
    if sales_orders.empty:
        return []
    dates = pd.to_datetime(sales_orders["order_date"])
    start, end = str(dates.min().date()), str(dates.max().date())
    fulfilled = int((sales_orders["status"] == "fulfilled").sum())
    total = len(sales_orders)
    _ = sales_lines
    return [KPIResult(
        "order_fulfillment_rate", fulfilled / total if total else None, "ratio",
        float(fulfilled), float(total), start, end, "dataset", {},
        ["sales_orders"], True, "formula=status==fulfilled over orders",
        "Status-based proxy; schema has no fulfilled quantities.",
    )]


def demand_fulfillment_rate(demand: pd.DataFrame, sales_lines: pd.DataFrame) -> list[KPIResult]:
    """Sold units over demanded units at the dataset grain."""
    if demand.empty or sales_lines.empty:
        return [KPIResult(
            "demand_fulfillment_rate", None, "ratio", None, None, "", "", "dataset",
            {}, ["demand_observations", "sales_order_lines"], True,
            "formula=sold/demanded",
            "Undefined without demand and sales in range.",
        )]
    sold = float(sales_lines["quantity"].astype(float).sum())
    demanded = float(demand["quantity"].sum())
    dates = pd.to_datetime(demand["date"])
    start, end = str(dates.min().date()), str(dates.max().date())
    return [KPIResult(
        "demand_fulfillment_rate", sold / demanded if demanded else None, "ratio",
        sold, demanded, start, end, "dataset", {},
        ["demand_observations", "sales_order_lines"], True,
        "formula=sum(sold)/sum(demanded)",
        "Dataset-level ratio; shortfalls are lost sales in generation.",
    )]


def stockout_rate_from_snapshots(snapshots: pd.DataFrame) -> list[KPIResult]:
    """Share of snapshots with zero on-hand."""
    if snapshots.empty:
        return []
    dates = pd.to_datetime(snapshots["snapshot_date"])
    start, end = str(dates.min().date()), str(dates.max().date())
    zeros = int((snapshots["on_hand"].astype(float) == 0).sum())
    total = len(snapshots)
    return [KPIResult(
        "service_stockout_rate", zeros / total if total else None, "ratio",
        float(zeros), float(total), start, end, "dataset", {},
        ["inventory_snapshots"], True, "formula=zero snapshots/total",
        "Availability proxy from generated snapshots.",
    )]
