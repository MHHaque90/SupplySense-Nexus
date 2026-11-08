"""Phase 4 routing and decomposition tests."""

from backend.app.analytics.forecasting.decomposition import assess_trend, detect_seasonality
from backend.app.analytics.forecasting.routing import route_series


def test_zero_series_routes_to_zero():
    profile, candidates, _ = route_series([0.0] * 100)
    assert profile.profile == "zero"
    assert candidates == ["zero"]


def test_constant_series_avoids_complex_models():
    profile, candidates, _ = route_series([7.0] * 100)
    assert profile.profile == "constant"
    assert set(candidates) <= {"naive", "moving_average", "ses"}
    assert "holt_winters" not in candidates and "hgb" not in candidates


def test_trending_series_routes_to_trend_models():
    profile, candidates, _ = route_series([10.0 + 0.5 * i for i in range(120)])
    assert profile.profile == "trending"
    assert {"drift", "holt", "autoreg"} <= set(candidates)


def test_intermittent_series_routes_to_croston():
    series = [0.0] * 120
    series[::4] = [25.0] * 30
    profile, candidates, _ = route_series(series)
    assert profile.profile == "intermittent"
    assert "croston" in candidates


def test_stable_series_routes_to_smoothing_models():
    series = [10.0, 11.0, 9.0, 10.5, 9.5] * 24
    profile, candidates, _ = route_series(series)
    assert profile.profile == "stable"
    assert {"naive", "moving_average", "ses", "holt"} <= set(candidates)


def test_short_history_gates_complex_models():
    profile, candidates, reasons = route_series([5.0, 6.0, 5.5, 6.5, 5.0])
    assert "holt_winters" not in candidates
    assert "autoreg" not in candidates
    assert any("excluded" in reason for reason in reasons)
    assert candidates, "Fallback must always leave a candidate"


def test_ml_opt_in_required():
    stable = [10.0, 11.0, 9.0, 10.5, 9.5] * 24
    _, without, _ = route_series(stable)
    _, with_ml, _ = route_series(stable, include_ml=True)
    assert "hgb" not in without
    assert "hgb" in with_ml


def test_generator_profile_never_used_as_truth():
    # Observed statistics drive routing even when they disagree with
    # any hypothetical source label: flat data routes to constant.
    profile, candidates, _ = route_series([4.0] * 90)
    assert profile.profile == "constant"
    assert "croston" not in candidates


def test_trend_assessment_direction_and_strength():
    up = assess_trend([float(i) for i in range(50)])
    assert up.direction == "up" and up.slope_per_day > 0
    assert 0.0 <= up.r_squared <= 1.0
    down = assess_trend([float(50 - i) for i in range(50)])
    assert down.direction == "down"
    flat = assess_trend([5.0] * 50)
    assert flat.direction == "flat" and flat.slope_per_day == 0.0
    assert flat.normalized_slope is not None


def test_seasonality_detection_needs_history():
    short = detect_seasonality([10.0] * 10, periods=(7,))
    assert short.period is None
    assert short.sufficient_history is False
    weekly = [20.0 if i % 7 < 5 else 5.0 for i in range(70)]
    found = detect_seasonality(weekly, periods=(7,))
    assert found.period == 7
    assert found.sufficient_history is True
    flat = detect_seasonality([10.0] * 70, periods=(7,))
    assert flat.period is None
