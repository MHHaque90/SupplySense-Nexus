"""Phase 3 walk-forward validation tests."""

import pytest

from backend.app.analytics.forecasting.baselines import Naive, SeasonalNaive
from backend.app.analytics.forecasting.validation import (
    compare_models,
    default_baselines,
    walk_forward,
)
from backend.app.analytics.types import InsufficientHistoryError


def test_temporal_ordering_and_fold_count():
    series = list(range(1, 101))
    folds = walk_forward(
        series, {"naive": Naive()}, horizon=10, step=10, min_history=50,
        metric_names=("mae",), series_id="S",
    )
    assert [f.train_length for f in folds] == [50, 60, 70, 80, 90]
    assert all(len(f.actuals) == 10 and len(f.predictions) == 10 for f in folds)
    first = folds[0]
    assert first.actuals[0] == 51.0
    assert first.predictions[0] == 50.0


def test_no_future_leakage():
    series = [10.0] * 50 + [1000.0] * 50
    folds = walk_forward(
        series, {"naive": Naive()}, horizon=5, step=45, min_history=50,
        metric_names=("mae",), series_id="S",
    )
    assert folds[0].predictions == [10.0] * 5  # spike invisible during training


def test_multiple_models_and_metrics():
    series = [float(i % 7) for i in range(120)]
    models = default_baselines(season=7)
    folds = walk_forward(series, models, horizon=7, step=30, min_history=60,
                         metric_names=("mae", "rmse", "smape"))
    assert {f.model_name for f in folds} == set(models)
    assert all(set(f.metrics) == {"mae", "rmse", "smape"} for f in folds)


def test_insufficient_history_rejected():
    with pytest.raises(InsufficientHistoryError):
        walk_forward([1.0] * 20, {"naive": Naive()}, horizon=10, step=5, min_history=15)
    with pytest.raises(ValueError):
        walk_forward([1.0] * 50, {"naive": Naive()}, horizon=0, step=5, min_history=10)


def test_short_models_skipped_not_failed():
    series = [float(i) for i in range(60)]
    folds = walk_forward(
        series,
        {"naive": Naive(), "seasonal_naive": SeasonalNaive(season=7)},
        horizon=7, step=20, min_history=10, metric_names=("mae",),
    )
    # Seasonal naive needs season=7; min_history=10 covers cutoffs 10..53.
    assert {f.model_name for f in folds} == {"naive", "seasonal_naive"}


def test_deterministic_output():
    series = [float((i * 37) % 11) for i in range(150)]
    first = walk_forward(series, default_baselines(), horizon=14, step=14,
                         min_history=80, metric_names=("mae", "wape"))
    second = walk_forward(series, default_baselines(), horizon=14, step=14,
                          min_history=80, metric_names=("mae", "wape"))
    assert [f.to_dict() for f in first] == [f.to_dict() for f in second]


def test_compare_models_selects_lowest_error():
    series = [10.0 + (i % 7) for i in range(200)]
    comparison = compare_models(series, horizon=7, step=30, min_history=100,
                                metric="mae", series_id="S", season=7)
    assert comparison.selected_model == "seasonal_naive"
    assert "lowest observed validation error" in comparison.note.lower()
    assert comparison.scores["seasonal_naive"] < comparison.scores["naive"]


def test_compare_models_records_skips():
    comparison = compare_models([1.0, 2.0, 3.0], horizon=7, step=7,
                                min_history=10, series_id="short")
    assert comparison.selected_model is None
    assert comparison.skipped, "Expected skip reasons for short series"
