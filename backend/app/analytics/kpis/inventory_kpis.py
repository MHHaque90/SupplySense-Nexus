"""Inventory KPIs (Phase 3).

Quantity-based only: unit costs exist in the schema but are unreliable
as a valuation basis (stored as free-form strings), so no monetary
inventory value is reported. Reconciliation replays the transaction
ledger per product/warehouse.
"""

import pandas as pd

from backend.app.analytics.types import KPIResult

SOURCES = ["inventory_snapshots", "inventory_transactions"]
_SIGNED = {
    "OPENING_BALANCE": 1.0, "RECEIPT": 1.0, "TRANSFER_IN": 1.0,
    "RETURN": 1.0, "ADJUSTMENT": 1.0, "SALE": -1.0, "TRANSFER_OUT": -1.0,
}


def _latest_per_series(snapshots: pd.DataFrame) -> pd.DataFrame:
    ordered = snapshots.sort_values("snapshot_date")
    return ordered.groupby(["product_id", "warehouse_id"], as_index=False).tail(1)


def current_on_hand(snapshots: pd.DataFrame) -> list[KPIResult]:
    """Report the latest on-hand quantity per product/warehouse."""
    if snapshots.empty:
        return []
    latest = _latest_per_series(snapshots)
    end = str(pd.to_datetime(latest["snapshot_date"]).max().date())
    return [
        KPIResult(
            "current_on_hand", float(row["on_hand"]), "units", float(row["on_hand"]), None,
            end, end, "snapshot",
            {"product_id": str(row["product_id"]), "warehouse_id": str(row["warehouse_id"])},
            ["inventory_snapshots"], True, "formula=latest available_qty",
            "Latest observed snapshot for the series.",
        )
        for _, row in latest.iterrows()
    ]


def inventory_levels(snapshots: pd.DataFrame) -> list[KPIResult]:
    """Compute average/min/max/volatility of on-hand across snapshots."""
    if snapshots.empty:
        return []
    start = str(pd.to_datetime(snapshots["snapshot_date"]).min().date())
    end = str(pd.to_datetime(snapshots["snapshot_date"]).max().date())
    values = snapshots["on_hand"].astype(float)
    stats = [
        ("average_inventory", float(values.mean()), "formula=mean(available_qty)"),
        ("minimum_inventory", float(values.min()), "formula=min(available_qty)"),
        ("maximum_inventory", float(values.max()), "formula=max(available_qty)"),
        ("inventory_volatility", float(values.std(ddof=0) or 0.0), "formula=std(available_qty)"),
    ]
    return [
        KPIResult(name, value, "units", None, None, start, end, "dataset", {},
                  ["inventory_snapshots"], True, formula,
                  "Observed generated snapshot levels.")
        for name, value, formula in stats
    ]


def stockout_stats(snapshots: pd.DataFrame) -> list[KPIResult]:
    """Count zero on-hand snapshots and their rate."""
    if snapshots.empty:
        return []
    start = str(pd.to_datetime(snapshots["snapshot_date"]).min().date())
    end = str(pd.to_datetime(snapshots["snapshot_date"]).max().date())
    zeros = int((snapshots["on_hand"].astype(float) == 0).sum())
    total = len(snapshots)
    return [
        KPIResult("stockout_snapshots", float(zeros), "count", float(zeros), None,
                  start, end, "dataset", {}, ["inventory_snapshots"], True,
                  "formula=count(available_qty==0)",
                  "Snapshots with zero on-hand in the synthetic dataset."),
        KPIResult("stockout_rate", zeros / total if total else None, "ratio",
                  float(zeros), float(total), start, end, "dataset", {},
                  ["inventory_snapshots"], True, "formula=zeros/total",
                  "Share of snapshots with zero on-hand."),
        KPIResult("zero_inventory_days", float(snapshots.loc[
            snapshots["on_hand"].astype(float) == 0, "snapshot_date"].nunique()),
                  "days", None, None, start, end, "dataset", {},
                  ["inventory_snapshots"], True, "formula=distinct dates with zero",
                  "Calendar days with at least one stocked-out series."),
    ]


def turnover_proxy(transactions: pd.DataFrame, snapshots: pd.DataFrame) -> list[KPIResult]:
    """Compute sales / average-inventory turnover proxy.

    Labeled a proxy: the schema has no cost-of-goods-sold, so this uses
    outbound units over mean on-hand units.
    """
    if transactions.empty or snapshots.empty:
        return []
    sales = transactions[transactions["transaction_type"] == "SALE"]["quantity"].astype(float).sum()
    avg_inv = snapshots["on_hand"].astype(float).mean()
    value = float(sales / avg_inv) if avg_inv else None
    start = str(pd.to_datetime(snapshots["snapshot_date"]).min().date())
    end = str(pd.to_datetime(snapshots["snapshot_date"]).max().date())
    return [KPIResult(
        "inventory_turnover_proxy", value, "ratio", float(sales),
        float(avg_inv) if avg_inv else None, start, end, "dataset", {},
        SOURCES, True, "formula=sum(sale_qty)/mean(on_hand)",
        "Unit-based proxy; not a financial turnover ratio.",
    )]


def days_of_supply(
    snapshots: pd.DataFrame, average_daily_demand: float
) -> list[KPIResult]:
    """Compute mean on-hand over average daily demand, where valid."""
    if snapshots.empty or average_daily_demand <= 0:
        return [KPIResult(
            "days_of_supply", None, "days", None, None, "", "", "dataset", {},
            ["inventory_snapshots", "demand_observations"], True,
            "formula=mean(on_hand)/avg_daily_demand",
            "Undefined without positive average demand.",
        )]
    value = float(snapshots["on_hand"].astype(float).mean() / average_daily_demand)
    start = str(pd.to_datetime(snapshots["snapshot_date"]).min().date())
    end = str(pd.to_datetime(snapshots["snapshot_date"]).max().date())
    return [KPIResult(
        "days_of_supply", value, "days", float(snapshots["on_hand"].astype(float).mean()),
        float(average_daily_demand), start, end, "dataset", {},
        ["inventory_snapshots", "demand_observations"], True,
        "formula=mean(on_hand)/avg_daily_demand",
        "Coverage implied by generated levels and demand.",
    )]


def movement_summary(transactions: pd.DataFrame) -> list[KPIResult]:
    """Summarize signed inflows, outflows, and net movement."""
    if transactions.empty:
        return []
    signed = transactions["quantity"].astype(float) * transactions["transaction_type"].map(
        lambda t: _SIGNED.get(str(t), 0.0)
    )
    inflow = float(signed[signed > 0].sum())
    outflow = float(-signed[signed < 0].sum())
    dates = pd.to_datetime(transactions["timestamp"])
    start, end = str(dates.min().date()), str(dates.max().date())
    return [
        KPIResult("inventory_inflow", inflow, "units", inflow, None, start, end,
                  "dataset", {}, ["inventory_transactions"], True,
                  "formula=sum(receipts+opening+adjustments)",
                  "Observed generated inbound movement."),
        KPIResult("inventory_outflow", outflow, "units", outflow, None, start, end,
                  "dataset", {}, ["inventory_transactions"], True,
                  "formula=sum(sales)", "Observed generated outbound movement."),
        KPIResult("inventory_net_movement", inflow - outflow, "units", inflow, outflow,
                  start, end, "dataset", {}, ["inventory_transactions"], True,
                  "formula=inflow-outflow", "Net generated movement."),
    ]


def reconciliation_status(
    transactions: pd.DataFrame, snapshots: pd.DataFrame, tolerance: float = 0.01
) -> list[KPIResult]:
    """Replay the ledger and compare against closing snapshots."""
    if transactions.empty or snapshots.empty:
        return []
    ledger: dict[tuple[str, str], float] = {}
    for _, row in transactions.iterrows():
        key = (str(row["product_id"]), str(row["warehouse_id"]))
        sign = _SIGNED.get(str(row["transaction_type"]), 0.0)
        ledger[key] = ledger.get(key, 0.0) + sign * float(row["quantity"])
    latest = snapshots.sort_values("snapshot_date").groupby(
        ["product_id", "warehouse_id"], as_index=False).tail(1)
    mismatches = sum(
        1 for _, row in latest.iterrows()
        if abs(ledger.get((str(row["product_id"]), str(row["warehouse_id"])), 0.0)
               - float(row["on_hand"])) > tolerance
    )
    end = str(pd.to_datetime(latest["snapshot_date"]).max().date())
    return [KPIResult(
        "inventory_reconciled_series", float(len(latest) - mismatches), "count",
        float(len(latest) - mismatches), float(len(latest)), "", end, "dataset", {},
        SOURCES, True, "formula=series where |ledger-closing|<=tol",
        "Ledger replay vs closing snapshots in generated data.",
    )]
