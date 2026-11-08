"""Phase 4 forecast output contract tests."""

from backend.app.analytics.forecasting.result import ForecastOutput, SelectionResult


def _output(**overrides):
    base = {
        "series_id": "P|W", "product_id": "P", "warehouse_id": "W",
        "origin": "2026-06-30",
        "forecast_dates": ["2026-07-01", "2026-07-02"], "horizon": 2,
        "model_name": "seasonal_naive", "point": [10.0, 12.0],
        "lower": [8.0, 9.0], "upper": [12.0, 15.0], "confidence_level": 0.95,
        "demand_profile": "stable", "validation_metric": "mae",
        "validation_score": 1.5, "validation_folds": 5,
        "training_start": "2025-07-01", "training_end": "2026-06-30",
    }
    base.update(overrides)
    return ForecastOutput(**base)


def test_contract_fields_and_defaults():
    output = _output()
    assert output.synthetic is True
    assert output.interval_method == "empirical_residual_quantile"
    assert output.assumptions == [] and output.warnings == []
    payload = output.to_dict()
    assert payload["series_id"] == "P|W"
    assert payload["horizon"] == 2
    assert len(payload["point"]) == len(payload["lower"]) == len(payload["upper"]) == 2


def test_selection_result_contract():
    selection = SelectionResult(
        series_id="P|W", product_id="P", warehouse_id="W", selected_model="holt",
        fallback_used=False, validation_metric="mae", validation_score=2.0,
        validation_folds=4, demand_profile="trending",
    )
    payload = selection.to_dict()
    assert payload["candidates"] == [] and payload["skipped"] == {}
    assert payload["model_config"] == {}
    assert "lowest observed" in payload.get("explanation", "") or payload["explanation"] == ""


def test_point_forecasts_floored_in_assembly():
    # Contract assembly floors negatives; models themselves stay raw.
    from datetime import date

    from backend.app.analytics.config import AnalyticsConfig
    from backend.app.analytics.reports.forecasting_report import evaluate_one_series

    values = [50.0 - i for i in range(120)]  # steep decline -> negative drift
    evaluation = evaluate_one_series(
        values, "P|W", "P", "W", date(2026, 6, 30),
        AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60),
    )
    assert all(v >= 0 for v in evaluation["forecast"]["point"])
    assert all(v >= 0 for v in evaluation["forecast"]["lower"])
    assert evaluation["forecast"]["synthetic"] is True
