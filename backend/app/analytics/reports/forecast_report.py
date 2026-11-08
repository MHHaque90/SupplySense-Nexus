"""Baseline forecast evaluation section (Phase 3)."""

from typing import Any

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.forecasting.validation import (
    compare_models,
    default_baselines,
    walk_forward,
)


def evaluate_series(
    values: list[float],
    series_id: str,
    config: AnalyticsConfig,
    season: int = 7,
    cutoff_labels: list[str] | None = None,
) -> dict[str, Any]:
    """Walk-forward evaluation of all baselines on one series."""
    models = default_baselines(season=season, alpha=config.ses_alpha)
    folds = walk_forward(
        values,
        models,
        horizon=config.forecast_horizon,
        step=config.validation_step,
        min_history=config.min_history,
        metric_names=("mae", "rmse", "smape", "wape", "bias"),
        series_id=series_id,
        cutoff_labels=cutoff_labels,
    )
    comparison = compare_models(
        values,
        horizon=config.forecast_horizon,
        step=config.validation_step,
        min_history=config.min_history,
        metric=config.comparison_metric,
        series_id=series_id,
        season=season,
    )
    by_model: dict[str, dict[str, Any]] = {}
    for fold in folds:
        entry = by_model.setdefault(fold.model_name, {"folds": 0, "metrics": {}})
        entry["folds"] += 1
        for metric_name, value in fold.metrics.items():
            if value is None:
                continue
            accumulator = entry["metrics"].setdefault(metric_name, [])
            accumulator.append(value)
    summary = {
        model: {
            "folds": payload["folds"],
            "metrics": {m: sum(v) / len(v) for m, v in payload["metrics"].items()},
        }
        for model, payload in by_model.items()
    }
    return {
        "series_id": series_id,
        "cutoffs": sorted({fold.cutoff for fold in folds}),
        "model_summary": summary,
        "comparison": comparison.to_dict(),
    }
