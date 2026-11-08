"""Phase 3 baseline forecasting tests."""

import pytest

from backend.app.analytics.forecasting.baselines import (
    BASELINE_MODELS,
    Drift,
    MovingAverage,
    Naive,
    SeasonalNaive,
    SimpleExponentialSmoothing,
)
from backend.app.analytics.types import InsufficientHistoryError


def test_naive_repeats_last():
    result = Naive().fit([1.0, 2.0, 5.0]).predict(3)
    assert result.predictions == [5.0, 5.0, 5.0]
    assert result.model_name == "naive"


def test_seasonal_naive_tiles_cycle():
    result = SeasonalNaive(season=3).fit([1.0, 2.0, 3.0, 4.0]).predict(5)
    assert result.predictions == [2.0, 3.0, 4.0, 2.0, 3.0]


def test_seasonal_naive_rejects_short_history():
    with pytest.raises(InsufficientHistoryError):
        SeasonalNaive(season=7).fit([1.0, 2.0, 3.0])


def test_moving_average_window():
    result = MovingAverage(window=3).fit([1.0, 2.0, 3.0, 4.0]).predict(2)
    assert result.predictions == [3.0, 3.0]
    with pytest.raises(InsufficientHistoryError):
        MovingAverage(window=5).fit([1.0, 2.0])


def test_drift_extrapolates_slope():
    result = Drift().fit([2.0, 4.0, 6.0]).predict(2)
    assert result.predictions == [8.0, 10.0]
    with pytest.raises(InsufficientHistoryError):
        Drift().fit([2.0])


def test_ses_converges_and_validates_alpha():
    result = SimpleExponentialSmoothing(alpha=1.0).fit([1.0, 5.0]).predict(1)
    assert result.predictions == [5.0]
    with pytest.raises(ValueError):
        SimpleExponentialSmoothing(alpha=0.0)
    with pytest.raises(ValueError):
        SimpleExponentialSmoothing(alpha=1.5)


def test_empty_history_rejected():
    with pytest.raises(InsufficientHistoryError):
        Naive().fit([])


def test_invalid_horizon_rejected():
    with pytest.raises(ValueError):
        Naive().fit([1.0]).predict(0)


def test_all_baselines_registered():
    assert set(BASELINE_MODELS) == {"naive", "seasonal_naive", "moving_average", "drift", "ses"}
    for name, cls in BASELINE_MODELS.items():
        model = cls() if name not in ("seasonal_naive", "moving_average", "ses") else None
        assert model is None or model.name == name
