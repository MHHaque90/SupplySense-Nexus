"""Current inventory position analytics (Phase 5).

Point-in-time discipline: only snapshots and transactions on or before
the analysis date are used. Warehouses are never combined.
"""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory.types import InventoryIntelligenceConfig, InventoryPosition

_SIGNED = {
    "OPENING_BALANCE": 1.0, "RECEIPT": 1.0, "TRANSFER_IN": 1.0,
    "RETURN": 1.0, "ADJUSTMENT": 1.0, "SALE": -1.0, "TRANSFER_OUT": -1.0,
}


def describe_position(
    product_id: str,
    warehouse_id: str,
    snapshots: pd.DataFrame,
    transactions: pd.DataFrame,
    analysis_date: date,
    config: InventoryIntelligenceConfig,
) -> InventoryPosition:
    """Describe the inventory position known at the analysis date."""
    analysis = analysis_date.isoformat()
    series_snaps = snapshots[
        (snapshots["product_id"] == product_id)
        & (snapshots["warehouse_id"] == warehouse_id)
        & (pd.to_datetime(snapshots["snapshot_date"]).dt.date <= analysis_date)
    ].sort_values("snapshot_date")
    if series_snaps.empty:
        return InventoryPosition(
            product_id=product_id, warehouse_id=warehouse_id,
            analysis_date=analysis, current_on_hand=None,
            latest_snapshot_date=None, unknown=True,
        )
    latest = series_snaps.iloc[-1]
    window_start = analysis_date.fromordinal(analysis_date.toordinal() - config.recent_window_days)
    recent = series_snaps[
        pd.to_datetime(series_snaps["snapshot_date"]).dt.date >= window_start
    ]
    recent_values = recent["on_hand"].astype(float)
    series_txns = transactions[
        (transactions["product_id"] == product_id)
        & (transactions["warehouse_id"] == warehouse_id)
        & (pd.to_datetime(transactions["timestamp"]).dt.date <= analysis_date)
        & (pd.to_datetime(transactions["timestamp"]).dt.date >= window_start)
    ]
    signed = series_txns["quantity"].astype(float) * series_txns["transaction_type"].map(
        lambda t: _SIGNED.get(str(t), 0.0)
    )
    return InventoryPosition(
        product_id=product_id,
        warehouse_id=warehouse_id,
        analysis_date=analysis,
        current_on_hand=float(latest["on_hand"]),
        latest_snapshot_date=str(latest["snapshot_date"]),
        recent_average=float(recent_values.mean()) if len(recent_values) else None,
        recent_minimum=float(recent_values.min()) if len(recent_values) else None,
        recent_maximum=float(recent_values.max()) if len(recent_values) else None,
        recent_volatility=float(recent_values.std(ddof=0) or 0.0) if len(recent_values) else None,
        recent_inflow=float(signed[signed > 0].sum()),
        recent_outflow=float(-signed[signed < 0].sum()),
        adjustment_count=int((series_txns["transaction_type"] == "ADJUSTMENT").sum()),
        stockout_observations=int((series_snaps["on_hand"].astype(float) == 0).sum()),
    )
