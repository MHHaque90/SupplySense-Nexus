"""Phase 4 prediction interval tests."""

import pytest

from backend.app.analytics.forecasting.intervals import (
    SUPPORTED_LEVELS,
    build_intervals,
    collect_residuals,
    interval_score,
    residual_quantiles,
)
from backend.app.analytics.forecasting.result import ValidationFold


def _folds():
    return [
        ValidationFold("m", "S", "c1", 3, [10.0, 12.0, 11.0], [9.0, 13.0, 11.0],
                       {"mae": 1.0}, 50),
        ValidationFold("m", "S", "c2", 3, [9.0, 9.0, 10.0], [10.0, 8.0, 10.0],
                       {"mae": 1.0}, 60),
    ]


def test_interval_ordering_and_support():
    assert SUPPORTED_LEVELS == (0.8, 0.95)
    residuals = collect_residuals(_folds(), "m")
    assert len(residuals) == 6
    result = build_intervals([10.0, 10.0, 10.0], residuals, 0.95,
                             actuals=[10.0, 12.0, 11.0])
    for low, point, high in zip(result.lower, [10.0] * 3, result.upper):
        assert low <= point <= high
    assert result.in_sample_coverage is not None
    assert result.mean_width is not None and result.mean_width >= 0


def test_narrower_level_gives_narrower_intervals():
    residuals = [-3.0, -1.0, 0.0, 1.0, 3.0] * 4
    narrow = build_intervals([10.0], residuals, 0.8)
    wide = build_intervals([10.0], residuals, 0.95)
    assert (wide.upper[0] - wide.lower[0]) >= (narrow.upper[0] - narrow.lower[0])


def test_lower_bounds_floored_at_zero():
    residuals = [-50.0, 50.0]
    result = build_intervals([1.0], residuals, 0.8)
    assert result.lower[0] == 0.0
    assert all(v == v for v in result.lower + result.upper)


def test_zero_demand_series_intervals_finite():
    result = build_intervals([0.0, 0.0], [0.0] * 10, 0.95)
    assert result.lower == [0.0, 0.0] and result.upper == [0.0, 0.0]


def test_unsupported_level_and_empty_residuals_rejected():
    with pytest.raises(ValueError):
        residual_quantiles([1.0], 0.9)
    with pytest.raises(ValueError):
        residual_quantiles([], 0.95)


def test_interval_score_penalizes_misses():
    tight_hit = interval_score([10.0], [9.0], [11.0], 0.95)
    wide_miss = interval_score([20.0], [9.0], [11.0], 0.95)
    assert wide_miss > tight_hit
    with pytest.raises(ValueError):
        interval_score([], [], [])


def test_collect_residuals_filters_model():
    other = ValidationFold("other", "S", "c1", 1, [5.0], [5.0], {"mae": 0.0}, 10)
    assert collect_residuals([* _folds(), other], "other") == [0.0]
