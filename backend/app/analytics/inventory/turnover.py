"""Turnover and concentration analytics (Phase 5).

Extends the Phase 3 unit turnover proxy per series and adds
descriptive inventory concentration. Quantity-based only: the schema
has no reliable valuation basis, so no monetary values are reported.
Concentration is descriptive; it never recommends transfers.
"""

import pandas as pd


def series_turnover(
    product_id: str,
    warehouse_id: str,
    transactions: pd.DataFrame,
    snapshots: pd.DataFrame,
) -> dict[str, float | None]:
    """Compute per-series turnover proxy and supporting quantities."""
    series_txns = transactions[
        (transactions["product_id"] == product_id)
        & (transactions["warehouse_id"] == warehouse_id)
    ]
    series_snaps = snapshots[
        (snapshots["product_id"] == product_id)
        & (snapshots["warehouse_id"] == warehouse_id)
    ]
    if series_txns.empty or series_snaps.empty:
        return {"turnover_proxy": None, "sales": None, "average_inventory": None}
    sales = float(series_txns[series_txns["transaction_type"] == "SALE"]["quantity"].astype(float).sum())
    average = float(series_snaps["on_hand"].astype(float).mean())
    return {
        "turnover_proxy": (sales / average) if average else None,
        "sales": sales,
        "average_inventory": average,
    }


def turnover_trend(
    product_id: str,
    warehouse_id: str,
    transactions: pd.DataFrame,
    snapshots: pd.DataFrame,
    split_days: int = 30,
) -> dict[str, float | None]:
    """Compare turnover proxy between the earlier and recent halves."""
    series_snaps = snapshots[
        (snapshots["product_id"] == product_id)
        & (snapshots["warehouse_id"] == warehouse_id)
    ].sort_values("snapshot_date")
    if series_snaps.empty:
        return {"early": None, "recent": None}
    latest = pd.to_datetime(series_snaps["snapshot_date"]).max()
    cutoff = (latest - pd.Timedelta(days=split_days)).date()
    early_snaps = series_snaps[pd.to_datetime(series_snaps["snapshot_date"]).dt.date < cutoff]
    recent_snaps = series_snaps[pd.to_datetime(series_snaps["snapshot_date"]).dt.date >= cutoff]
    series_txns = transactions[
        (transactions["product_id"] == product_id)
        & (transactions["warehouse_id"] == warehouse_id)
    ]
    early_sales = series_txns[
        pd.to_datetime(series_txns["timestamp"]).dt.date < cutoff
    ]
    recent_sales = series_txns[
        pd.to_datetime(series_txns["timestamp"]).dt.date >= cutoff
    ]

    def _ratio(sales: pd.DataFrame, snaps: pd.DataFrame) -> float | None:
        if sales.empty or snaps.empty:
            return None
        total = float(sales[sales["transaction_type"] == "SALE"]["quantity"].astype(float).sum())
        average = float(snaps["on_hand"].astype(float).mean())
        return (total / average) if average else None

    return {"early": _ratio(early_sales, early_snaps), "recent": _ratio(recent_sales, recent_snaps)}
