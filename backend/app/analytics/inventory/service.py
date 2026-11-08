"""Service-level inventory signals (Phase 5).

Consumes Phase 3 service KPIs per series where supported. A series
with adequate inventory but repeated recent stockouts surfaces a
warning that feeds health classification. No supplier causality is
inferred.
"""

import pandas as pd


def service_warning(
    product_id: str,
    warehouse_id: str,
    snapshots: pd.DataFrame,
    recent_window_days: int = 30,
    stockout_threshold: int = 2,
) -> tuple[bool, str]:
    """Flag series with repeated recent stockouts despite current levels."""
    series = snapshots[
        (snapshots["product_id"] == product_id)
        & (snapshots["warehouse_id"] == warehouse_id)
    ]
    if series.empty:
        return False, "No snapshot history for service assessment."
    latest = pd.to_datetime(series["snapshot_date"]).max().date()
    cutoff = latest.fromordinal(latest.toordinal() - recent_window_days)
    recent = series[pd.to_datetime(series["snapshot_date"]).dt.date >= cutoff]
    stockouts = int((recent["on_hand"].astype(float) == 0).sum())
    if stockouts >= stockout_threshold:
        return True, (
            f"{stockouts} stockout observations in the last {recent_window_days} days; "
            "adequate current inventory does not erase recent service gaps."
        )
    return False, "No repeated recent stockouts in the observed generated records."
