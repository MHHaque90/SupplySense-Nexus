"""Demand feature engineering with explicit leakage control (Phase 3).

Continuity policy: :func:`ensure_daily_continuity` reindexes each
product/warehouse series onto the full calendar and fills gaps with
zero, recording the fill in ``was_imputed_zero``. Zero-fills are
documented imputation, not observed demand.
"""

import numpy as np
import pandas as pd

from backend.app.analytics.features.calendar_features import add_calendar_attributes

LAG_PERIODS = (1, 7, 14, 28)
ROLLING_WINDOWS = (7, 14, 28)


def ensure_daily_continuity(
    frame: pd.DataFrame,
    start: object | None = None,
    end: object | None = None,
) -> pd.DataFrame:
    """Reindex every product/warehouse series onto a complete daily calendar."""
    if frame.empty:
        work = frame.copy()
        work["was_imputed_zero"] = pd.Series(dtype=int)
        return work
    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.date
    start_date = pd.to_datetime(start or work["date"].min()).date()
    end_date = pd.to_datetime(end or work["date"].max()).date()
    calendar = pd.DataFrame(
        {"date": pd.date_range(start_date, end_date, freq="D").date}
    )
    keys = work[["product_id", "warehouse_id"]].drop_duplicates()
    full = keys.merge(calendar, how="cross")
    merged = full.merge(work, on=["product_id", "warehouse_id", "date"], how="left")
    merged["was_imputed_zero"] = merged["quantity"].isna().astype(int)
    merged["quantity"] = merged["quantity"].fillna(0.0).astype(float)
    return merged.sort_values(["product_id", "warehouse_id", "date"]).reset_index(drop=True)


def _grouped(frame: pd.DataFrame) -> pd.core.groupby.DataFrameGroupBy:
    return frame.sort_values(["product_id", "warehouse_id", "date"]).groupby(
        ["product_id", "warehouse_id"], sort=False
    )


def add_lag_features(frame: pd.DataFrame, lags: tuple[int, ...] = LAG_PERIODS) -> pd.DataFrame:
    """Add lag_k demand using only observations strictly before each date."""
    work = frame.copy()
    for lag in lags:
        work[f"lag_{lag}"] = _grouped(work)["quantity"].shift(lag)
    return work


def add_rolling_features(frame: pd.DataFrame, windows: tuple[int, ...] = ROLLING_WINDOWS) -> pd.DataFrame:
    """Add rolling mean/std over history strictly before each date.

    The series is shifted by one period before rolling so the current
    day's demand never leaks into its own features.
    """
    work = frame.copy()
    for window in windows:
        shifted = _grouped(work)["quantity"].shift(1)
        work[f"rolling_mean_{window}"] = shifted.groupby(
            [work["product_id"], work["warehouse_id"]], sort=False
        ).transform(lambda s: s.rolling(window, min_periods=1).mean()).to_numpy()
        if window in (7, 28):
            work[f"rolling_std_{window}"] = shifted.groupby(
                [work["product_id"], work["warehouse_id"]], sort=False
            ).transform(
                lambda s: s.rolling(window, min_periods=2).std(ddof=0)
            ).to_numpy()
    mean_28 = work.get("rolling_mean_28")
    std_28 = work.get("rolling_std_28")
    if mean_28 is not None and std_28 is not None:
        work["coefficient_of_variation"] = np.where(
            mean_28 > 0, std_28 / mean_28, np.nan
        )
    return work


def add_intermittent_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add zero-ratio, non-zero counts, and days-since-last-demand features."""
    work = frame.copy()
    grouped = _grouped(work)
    work["zero_ratio_28"] = grouped["quantity"].transform(
        lambda s: s.shift(1).rolling(28, min_periods=1).apply(lambda w: (w == 0).mean())
    ).to_numpy()
    work["nonzero_count_28"] = grouped["quantity"].transform(
        lambda s: s.shift(1).rolling(28, min_periods=1).apply(lambda w: (w > 0).sum())
    ).to_numpy()
    work["avg_demand_28"] = work.get("rolling_mean_28", np.nan)
    work["median_demand_28"] = grouped["quantity"].transform(
        lambda s: s.shift(1).rolling(28, min_periods=1).median()
    ).to_numpy()
    work["min_demand_28"] = grouped["quantity"].transform(
        lambda s: s.shift(1).rolling(28, min_periods=1).min()
    ).to_numpy()
    work["max_demand_28"] = grouped["quantity"].transform(
        lambda s: s.shift(1).rolling(28, min_periods=1).max()
    ).to_numpy()

    def _days_since(series: pd.Series) -> pd.Series:
        elapsed: int | None = None
        out: list[float] = []
        for value in series.tolist():
            out.append(np.nan if elapsed is None else float(elapsed + 1))
            if value > 0:
                elapsed = 0
            elif elapsed is not None:
                elapsed += 1
        return pd.Series(out, index=series.index)

    work["days_since_nonzero"] = grouped["quantity"].transform(_days_since).to_numpy()
    return work


def add_trend_feature(frame: pd.DataFrame, window: int = 28) -> pd.DataFrame:
    """Add the OLS slope of the trailing window (history only)."""
    work = frame.copy()

    def _slope(values: np.ndarray) -> float:
        series = np.asarray(values, dtype=float)
        if len(series) < 2 or np.all(series == series[0]):
            return 0.0
        xpos = np.arange(len(series))
        slope, _ = np.polyfit(xpos, series, 1)
        return float(slope)

    work["trend_slope_28"] = _grouped(work)["quantity"].transform(
        lambda s: s.shift(1).rolling(window, min_periods=2).apply(_slope, raw=True)
    ).to_numpy()
    return work


def build_feature_frame(
    frame: pd.DataFrame,
    lags: tuple[int, ...] = LAG_PERIODS,
    windows: tuple[int, ...] = ROLLING_WINDOWS,
) -> pd.DataFrame:
    """Build the full leakage-safe feature frame for demand modeling."""
    work = ensure_daily_continuity(frame)
    work = add_lag_features(work, lags)
    work = add_rolling_features(work, windows)
    work = add_intermittent_features(work)
    work = add_trend_feature(work)
    work = add_calendar_attributes(work, "date")
    return work
