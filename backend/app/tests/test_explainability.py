"""Phase 4 explainability tests."""

from backend.app.analytics.features.profiles import profile_series
from backend.app.analytics.forecasting.explainability import (
    confidence_descriptor,
    explain_selection,
    fallback_explanation,
    insufficient_history_explanation,
)
from backend.app.analytics.types import ModelComparison


def _comparison(model="holt", score=1.25):
    comparison = ModelComparison(series_id="S", metric="mae")
    comparison.scores = {model: score, "naive": 3.0}
    comparison.selected_model = model
    return comparison


def test_model_specific_explanation():
    profile = profile_series([10.0 + 0.3 * i for i in range(100)])
    text = explain_selection("holt", profile, _comparison("holt"))
    assert "Holt" in text and "trending" in text and "mae=1.250" in text


def test_seasonal_explanation():
    profile = profile_series([10.0 + (i % 7) for i in range(100)])
    text = explain_selection("seasonal_naive", profile, _comparison("seasonal_naive", 0.5))
    assert "Seasonal Naive" in text


def test_fallback_and_insufficient_history_explanations():
    assert "naive fallback used" in fallback_explanation("all models failed", "naive")
    message = insufficient_history_explanation(118, 20)
    assert "20" in message and "118" in message


def test_confidence_categories():
    assert confidence_descriptor(6, 0.1, 0.3, 0.05)["level"] == "strong validation support"
    assert confidence_descriptor(4, 0.3, 0.5, 0.1)["level"] == "moderate validation support"
    assert confidence_descriptor(1, 0.9, 1.2, 0.5)["level"] == "limited validation support"
    assert confidence_descriptor(0, None, None, 0.0)["level"] == "insufficient evidence"
    descriptor = confidence_descriptor(3, 0.2, 0.4, 0.0)
    assert set(descriptor["evidence"]) == {"folds", "validation_error", "volatility", "zero_ratio"}
