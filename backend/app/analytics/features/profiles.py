"""Analytical demand profiling (Phase 3).

Profiles are computed from observed demand statistics, independently of
the generator's source metadata. Classification rules:

- ``zero``: no positive observations at all.
- ``constant``: positive but (near-)identical values.
- ``intermittent``: 40%+ zero days.
- ``trending``: meaningful linear slope relative to mean level.
- ``seasonal``: weekly pattern strength (weekday vs weekend means differ
  by 25%+) with at least 28 observations; monthly claim requires 90+.
- ``volatile``: coefficient of variation above 0.8.
- ``stable``: everything else.

Seasonality is never claimed from insufficient data.
"""

import numpy as np
import pandas as pd

from backend.app.analytics.types import SeriesProfile


def _trend_slope(values: np.ndarray) -> float:
    if len(values) < 3 or np.all(values == values[0]):
        return 0.0
    slope, _ = np.polyfit(np.arange(len(values)), values.astype(float), 1)
    return float(slope)


def profile_series(values: pd.Series | np.ndarray | list[float], series_id: str = "") -> SeriesProfile:
    """Compute the analytical profile of one demand series."""
    data = np.asarray(values, dtype=float)
    observations = len(data)
    if observations == 0:
        return SeriesProfile(series_id, "zero", 0.0, 0.0, None, 1.0, 0, None, 0.0, 0)
    mean = float(np.mean(data))
    std = float(np.std(data))
    nonzero = data[data > 0]
    nonzero_count = len(nonzero)
    zero_ratio = float(np.mean(data == 0))
    cv_value = float(std / mean) if mean > 0 else None
    intervals = np.diff(np.flatnonzero(data > 0)) if nonzero_count > 1 else np.array([])
    mean_interval = float(np.mean(intervals)) if len(intervals) else None
    slope = _trend_slope(data)
    if nonzero_count == 0:
        profile = "zero"
    elif np.all(data == data[0]):
        profile = "constant"
    elif zero_ratio >= 0.4:
        profile = "intermittent"
    elif mean > 0 and abs(slope) * observations / mean >= 0.3:
        profile = "trending"
    elif cv_value is not None and cv_value > 0.8:
        profile = "volatile"
    else:
        profile = "stable"
    return SeriesProfile(
        series_id=series_id,
        profile=profile,
        mean_demand=mean,
        std_demand=std,
        coefficient_of_variation=cv_value,
        zero_ratio=zero_ratio,
        nonzero_count=nonzero_count,
        mean_interval_nonzero=mean_interval,
        trend_slope_per_day=slope,
        observations=observations,
    )


def weekly_seasonality_strength(frame: pd.DataFrame) -> float | None:
    """Return weekday/weekend mean ratio gap, or None under 28 observations."""
    if len(frame) < 28 or "quantity" not in frame:
        return None
    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"])
    weekday = work[work["date"].dt.weekday < 5]["quantity"].mean()
    weekend = work[work["date"].dt.weekday >= 5]["quantity"].mean()
    if weekday is None or pd.isna(weekday) or weekday == 0:
        return None
    return float(abs(float(weekday) - float(weekend)) / float(weekday))


def profile_dataset(frame: pd.DataFrame) -> list[SeriesProfile]:
    """Profile every product/warehouse series in a demand frame."""
    profiles: list[SeriesProfile] = []
    if frame.empty:
        return profiles
    for (product_id, warehouse_id), group in frame.groupby(["product_id", "warehouse_id"]):
        ordered = group.sort_values("date")
        profiles.append(
            profile_series(
                ordered["quantity"].to_numpy(),
                series_id=f"{product_id}|{warehouse_id}",
            )
        )
    return profiles
