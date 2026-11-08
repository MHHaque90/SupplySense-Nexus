"""Phase 4 ensemble tests."""

import pytest

from backend.app.analytics.forecasting.baselines import MovingAverage, Naive
from backend.app.analytics.forecasting.ensemble import (
    AverageEnsemble,
    WeightedEnsemble,
    inverse_error_weights,
)
from backend.app.analytics.forecasting.validation import walk_forward
from backend.app.analytics.types import InsufficientHistoryError


def test_inverse_error_weights_sum_to_one():
    weights = inverse_error_weights({"a": 2.0, "b": 6.0})
    assert weights == pytest.approx({"a": 0.75, "b": 0.25})
    assert sum(weights.values()) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        inverse_error_weights({})


def test_average_ensemble_means_members():
    history = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    result = AverageEnsemble({"naive": Naive(), "ma": MovingAverage(window=4)}).fit(history).predict(2)
    assert result.predictions == [7.25, 7.25]  # mean(8, 6.5)
    assert result.model_name == "ensemble_average"


def test_weighted_ensemble_applies_weights():
    history = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    result = WeightedEnsemble(
        {"naive": Naive(), "ma": MovingAverage(window=4)}, {"naive": 0.25, "ma": 0.75}
    ).fit(history).predict(1)
    assert result.predictions == [0.25 * 8.0 + 0.75 * 6.5]
    with pytest.raises(ValueError):
        WeightedEnsemble({"naive": Naive()}, {"naive": 1.0})
    with pytest.raises(ValueError):
        WeightedEnsemble(
            {"naive": Naive(), "ma": MovingAverage(window=4)}, {"naive": 0.5, "ma": 0.4}
        )


def test_ensemble_validated_like_any_model():
    series = [float(i % 7 + 10) for i in range(120)]
    members = {"naive": Naive(), "ma": MovingAverage(window=7)}
    folds = walk_forward(
        series, {"ensemble": AverageEnsemble(members)}, horizon=7, step=30,
        min_history=60, metric_names=("mae",),
    )
    assert folds and all(len(f.predictions) == 7 for f in folds)


def test_ensemble_rejects_empty_history():
    with pytest.raises(InsufficientHistoryError):
        AverageEnsemble({"naive": Naive(), "ma": MovingAverage(window=4)}).fit([])
