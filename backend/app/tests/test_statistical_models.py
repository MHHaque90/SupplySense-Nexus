"""Phase 4 statistical model tests: Holt, Holt-Winters, AR, Croston, Zero."""

import pytest

from backend.app.analytics.forecasting.models import (
    PHASE4_MODELS,
    AutoRegressor,
    Croston,
    GradientBoostingForecaster,
    HoltTrend,
    HoltWinters,
    ZeroForecast,
)
from backend.app.analytics.types import InsufficientHistoryError


def test_holt_extrapolates_trend():
    result = HoltTrend().fit([2.0, 4.0, 6.0, 8.0]).predict(2)
    assert result.model_name == "holt"
    assert result.predictions[1] > result.predictions[0] > 8.0
    with pytest.raises(InsufficientHistoryError):
        HoltTrend().fit([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        HoltTrend(alpha=0.0)


def test_holt_winters_repeats_seasonal_pattern():
    history = [10.0, 12.0, 14.0, 11.0, 13.0, 15.0, 12.0, 14.0]
    result = HoltWinters(season=4).fit(history).predict(4)
    assert len(result.predictions) == 4
    assert result.parameters["season"] == 4
    with pytest.raises(InsufficientHistoryError):
        HoltWinters(season=7).fit([1.0] * 10)


def test_autoreg_fits_linear_series():
    history = [float(i) for i in range(1, 31)]
    result = AutoRegressor(order=3).fit(history).predict(2)
    assert result.predictions[0] == pytest.approx(31.0, abs=0.5)
    with pytest.raises(InsufficientHistoryError):
        AutoRegressor(order=7).fit([1.0] * 10)


def test_croston_intermittent_rate():
    history = [0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0, 0.0]
    result = Croston(alpha=0.5).fit(history).predict(3)
    assert all(p > 0 for p in result.predictions)
    assert all(p < 10.0 for p in result.predictions)
    with pytest.raises(InsufficientHistoryError):
        Croston().fit([5.0])


def test_croston_all_zero_series():
    result = Croston().fit([0.0] * 20).predict(4)
    assert result.predictions == [0.0] * 4


def test_croston_sparse_demand_no_divide_by_zero():
    result = Croston().fit([0.0] * 99 + [50.0]).predict(2)
    assert all(v >= 0 and v != float("inf") for v in result.predictions)


def test_zero_forecast():
    assert ZeroForecast().fit([0.0] * 5).predict(3).predictions == [0.0] * 3
    assert ZeroForecast().fit([]).predict(1).predictions == [0.0]


def test_phase4_models_registered():
    assert set(PHASE4_MODELS) == {"zero", "holt", "holt_winters", "autoreg", "croston", "hgb"}
    assert GradientBoostingForecaster().name == "hgb"


def test_statistical_models_deterministic():
    history = [10.0 + (i % 5) + 0.1 * i for i in range(60)]
    for cls, kwargs in [(HoltTrend, {}), (HoltWinters, {"season": 7}),
                        (AutoRegressor, {"order": 5}), (Croston, {})]:
        first = cls(**kwargs).fit(history).predict(5).predictions
        second = cls(**kwargs).fit(history).predict(5).predictions
        assert first == second
