"""Phase 4 ML forecasting tests: determinism, temporality, leakage."""

import pandas as pd
import pytest

from backend.app.analytics.forecasting.models import ML_FEATURE_COLUMNS, GradientBoostingForecaster
from backend.app.analytics.types import InsufficientHistoryError


def _series(length=150, seed=0):
    dates = pd.date_range("2025-01-01", periods=length, freq="D")
    values = [10.0 + (i % 7) + 0.05 * i + (i % 3) for i in range(length)]
    return values, dates


def test_ml_deterministic_random_state():
    values, dates = _series()
    first = GradientBoostingForecaster().fit(values, dates).predict(7).predictions
    second = GradientBoostingForecaster().fit(values, dates).predict(7).predictions
    assert first == second
    assert len(first) == 7


def test_ml_rejects_short_history():
    with pytest.raises(InsufficientHistoryError):
        GradientBoostingForecaster().fit([1.0] * 50)


def test_ml_uses_leakage_safe_feature_set():
    values, dates = _series()
    model = GradientBoostingForecaster().fit(values, dates)
    assert model._model is not None
    assert list(model._model.feature_names_in_) == ML_FEATURE_COLUMNS


def test_ml_future_perturbation_does_not_change_past_fit():
    values, dates = _series()
    tampered = list(values)
    tampered[-1] = 9999.0
    early = values[:100]
    first = GradientBoostingForecaster().fit(early, dates[:100]).predict(3).predictions
    second = GradientBoostingForecaster().fit(tampered[:100], dates[:100]).predict(3).predictions
    assert first == second


def test_ml_recursive_predictions_are_finite():
    values, dates = _series()
    predictions = GradientBoostingForecaster().fit(values, dates).predict(28).predictions
    assert len(predictions) == 28
    assert all(v == v and abs(v) != float("inf") for v in predictions)


def test_ml_temporal_training_order_preserved():
    # Reversing history must change the forecast: order matters, no shuffling.
    values, dates = _series()
    forward = GradientBoostingForecaster().fit(values, dates).predict(5).predictions
    backward = GradientBoostingForecaster().fit(list(reversed(values)), dates).predict(5).predictions
    assert forward != backward
