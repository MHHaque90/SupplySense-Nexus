"""Phase 4 model selection tests."""

import pytest

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.forecasting.selection import build_model, model_family, select_model


def _config(**overrides):
    base = {"forecast_horizon": 7, "validation_step": 14, "min_history": 60}
    base.update(overrides)
    return AnalyticsConfig(**base)


def test_selects_seasonal_for_weekly_series():
    import pandas as pd

    dates = pd.date_range("2025-01-01", periods=200, freq="D")
    series = [20.0 if day.weekday() < 5 else 5.0 for day in dates]
    selection = select_model(series, "P|W", _config(), season=7, dates=dates)
    assert selection.selected_model == "seasonal_naive"
    assert selection.validation_folds >= 2
    assert selection.demand_profile in ("stable", "seasonal")
    assert not selection.fallback_used
    assert selection.product_id == "P" and selection.warehouse_id == "W"


def test_zero_series_selects_zero_without_fallback():
    selection = select_model([0.0] * 120, "P|W", _config())
    assert selection.selected_model == "zero"
    assert not selection.fallback_used


def test_short_series_falls_back_structured():
    selection = select_model([3.0, 4.0, 5.0], "P|W", _config())
    assert selection.fallback_used
    assert selection.selected_model in ("naive", "zero")
    assert selection.warnings, "Fallback must explain itself"


def test_force_model_runs_only_requested_model():
    series = [10.0 + (i % 7) for i in range(200)]
    selection = select_model(series, "P|W", _config(), force_model="naive")
    assert selection.candidates == ["naive"]
    assert selection.selected_model == "naive"
    with pytest.raises(ValueError):
        select_model(series, "P|W", _config(), force_model="no-such-model")


def test_failed_forced_model_falls_back():
    selection = select_model([1.0, 2.0], "P|W", _config(), force_model="holt_winters")
    assert selection.fallback_used
    assert selection.selected_model == "naive"


def test_selection_carries_audit_metadata():
    series = [10.0] * 120
    selection = select_model(series, "P|W", _config(), training_start="2025-01-01",
                             training_end="2025-04-30")
    assert selection.training_start == "2025-01-01"
    assert selection.training_end == "2025-04-30"
    assert selection.model_config["horizon"] == 7
    assert selection.explanation
    assert selection.confidence["level"] in (
        "strong validation support", "moderate validation support",
        "limited validation support", "insufficient evidence",
    )


def test_model_family_mapping():
    assert model_family("hgb") == "ml"
    assert model_family("holt_winters") == "statistical"
    assert model_family("croston") == "intermittent"
    assert model_family("naive") == "baseline"
    assert model_family("ensemble_average") == "ensemble"


def test_build_model_defaults():
    assert build_model("seasonal_naive", season=14).season == 14
    assert build_model("holt_winters", season=14).season == 14
    assert build_model("hgb").random_state == 0
