"""Phase 3 demand profiling tests."""

import pandas as pd

from backend.app.analytics.features.profiles import (
    profile_dataset,
    profile_series,
    weekly_seasonality_strength,
)


def test_stable_profile():
    series = [10.0, 11.0, 9.0, 10.5, 9.5, 10.0, 11.0, 10.0] * 5
    profile = profile_series(series, "S1")
    assert profile.profile == "stable"
    assert profile.observations == 40
    assert profile.coefficient_of_variation is not None and profile.coefficient_of_variation < 0.8


def test_trending_profile():
    series = [10.0 + 0.5 * i for i in range(60)]
    profile = profile_series(series, "T1")
    assert profile.profile == "trending"
    assert profile.trend_slope_per_day > 0


def test_volatile_profile():
    series = [5.0, 95.0] * 60  # high spread, no trend, no zeros
    profile = profile_series(series, "V1")
    assert profile.profile == "volatile"
    assert profile.coefficient_of_variation is not None
    assert profile.coefficient_of_variation > 0.8


def test_intermittent_profile():
    series = [0.0] * 60
    series[::5] = [20.0] * 12
    profile = profile_series(series, "I1")
    assert profile.profile == "intermittent"
    assert profile.zero_ratio >= 0.4
    assert profile.mean_interval_nonzero == 5.0


def test_constant_profile():
    profile = profile_series([7.0] * 30, "C1")
    assert profile.profile == "constant"
    assert profile.std_demand == 0.0


def test_zero_series_profile():
    profile = profile_series([0.0] * 30, "Z1")
    assert profile.profile == "zero"
    assert profile.nonzero_count == 0
    assert profile.zero_ratio == 1.0
    assert profile.coefficient_of_variation is None


def test_empty_series_safe():
    profile = profile_series([], "E1")
    assert profile.profile == "zero"
    assert profile.observations == 0


def test_seasonality_needs_sufficient_data():
    frame = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=10, freq="D"),
        "quantity": [10.0] * 10,
    })
    assert weekly_seasonality_strength(frame) is None
    frame = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=35, freq="D"),
        "quantity": [20.0 if d.weekday() < 5 else 5.0 for d in pd.date_range("2026-01-01", periods=35)],
    })
    strength = weekly_seasonality_strength(frame)
    assert strength is not None and strength > 0.25


def test_profile_dataset_groups_series():
    frame = pd.DataFrame({
        "product_id": ["P1"] * 30 + ["P2"] * 30,
        "warehouse_id": ["W1"] * 60,
        "date": list(pd.date_range("2026-01-01", periods=30)) * 2,
        "quantity": [10.0] * 30 + [0.0] * 30,
    })
    profiles = {p.series_id: p.profile for p in profile_dataset(frame)}
    assert profiles["P1|W1"] in ("stable", "constant")
    assert profiles["P2|W1"] == "zero"
    assert profile_dataset(frame.iloc[0:0]) == []
