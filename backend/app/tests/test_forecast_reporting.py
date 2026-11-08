"""Phase 4 forecasting report tests."""

from datetime import date

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.reports.forecasting_report import evaluate_dataset, render_markdown


def _series():
    payload = {}
    for index, base in enumerate([10.0, 50.0, 0.0]):
        values = [base + (i % 7) for i in range(120)] if base else [0.0] * 120
        payload[f"P{index}|W"] = {
            "values": values, "product_id": f"P{index}", "warehouse_id": "W",
            "training_start": "2025-01-01", "training_end": "2025-04-30",
        }
    return payload


def test_multi_series_report_structure():
    config = AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60)
    report = evaluate_dataset(_series(), date(2025, 4, 30), config)
    assert report["synthetic"] is True
    assert "SYNTHETIC DATA" in report["disclaimer"]
    assert report["series_evaluated"] == 3
    assert sum(report["model_usage"].values()) == 3
    assert report["fallback_count"] == 0
    assert report["mean_validation_score"] is not None
    assert report["mean_interval_width"] is not None
    assert len(report["evaluations"]) == 3
    assert report["limitations"]
    for evaluation in report["evaluations"]:
        assert len(evaluation["forecast"]["point"]) == 7
        assert evaluation["forecast"]["confidence_level"] == 0.95


def test_zero_series_in_report():
    config = AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60)
    report = evaluate_dataset(
        {"Z|W": {"values": [0.0] * 120, "product_id": "Z", "warehouse_id": "W",
                 "training_start": "2025-01-01", "training_end": "2025-04-30"}},
        date(2025, 4, 30), config,
    )
    assert report["evaluations"][0]["selection"]["selected_model"] == "zero"
    assert report["evaluations"][0]["forecast"]["point"] == [0.0] * 7


def test_max_series_limits_work():
    config = AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60)
    report = evaluate_dataset(_series(), date(2025, 4, 30), config, max_series=1)
    assert report["series_evaluated"] == 1


def test_markdown_report_wording():
    config = AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60)
    report = evaluate_dataset(_series(), date(2025, 4, 30), config)
    markdown = render_markdown(report)
    assert markdown.startswith("# SupplySense Nexus Forecasting Report")
    assert "SYNTHETIC" in markdown
    for banned in ("the company achieved", "the business will", "real demand"):
        assert banned not in markdown.lower()
