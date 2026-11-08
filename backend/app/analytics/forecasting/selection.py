"""Per-series model selection with structured fallback (Phase 4).

Selection runs routed candidates through the Phase 3 walk-forward
framework, requires successful fits, finite metrics, and at least one
validation fold, then picks the lowest-error model under the requested
metric. Wording stays narrow: selected for this series under this
validation configuration. If every candidate fails, a simple baseline
fallback is returned — never an error masquerading as a forecast.
"""

import numpy as np

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.forecasting import baselines, models
from backend.app.analytics.forecasting.explainability import (
    confidence_descriptor,
    explain_selection,
    fallback_explanation,
)
from backend.app.analytics.forecasting.result import SelectionResult
from backend.app.analytics.forecasting.routing import route_series
from backend.app.analytics.forecasting.validation import walk_forward
from backend.app.analytics.types import InsufficientHistoryError, ModelComparison

_MODEL_FACTORIES: dict[str, object] = {
    "naive": baselines.Naive,
    "seasonal_naive": baselines.SeasonalNaive,
    "moving_average": baselines.MovingAverage,
    "drift": baselines.Drift,
    "ses": baselines.SimpleExponentialSmoothing,
    "zero": models.ZeroForecast,
    "holt": models.HoltTrend,
    "holt_winters": models.HoltWinters,
    "autoreg": models.AutoRegressor,
    "croston": models.Croston,
    "hgb": models.GradientBoostingForecaster,
}

_MODEL_FAMILY: dict[str, str] = {
    "naive": "baseline", "seasonal_naive": "baseline", "moving_average": "baseline",
    "drift": "baseline", "ses": "baseline", "zero": "baseline",
    "holt": "statistical", "holt_winters": "statistical", "autoreg": "statistical",
    "croston": "intermittent", "hgb": "ml",
    "ensemble_average": "ensemble", "ensemble_weighted": "ensemble",
}


def model_family(model_name: str) -> str:
    """Return the model family for registry metadata."""
    return _MODEL_FAMILY.get(model_name, "unknown")


def build_model(model_name: str, season: int = 7):
    """Instantiate a candidate model by name with Phase 4 defaults."""
    if model_name == "seasonal_naive":
        return baselines.SeasonalNaive(season=season)
    if model_name == "holt_winters":
        return models.HoltWinters(season=season)
    factory = _MODEL_FACTORIES.get(model_name)
    if factory is None:
        raise ValueError(f"Unknown model: {model_name}")
    return factory()


def _split_ids(series_id: str) -> tuple[str, str]:
    parts = series_id.split("|")
    if len(parts) == 2:
        return parts[0], parts[1]
    return series_id, ""


def select_model(
    values: list[float],
    series_id: str,
    config: AnalyticsConfig | None = None,
    season: int = 7,
    include_ml: bool = False,
    training_start: str = "",
    training_end: str = "",
    force_model: str | None = None,
    dates: object | None = None,
) -> SelectionResult:
    """Select the lowest-error routed candidate for one series.

    With ``force_model``, only the requested model is attempted (it must
    be a known registry name); failure falls back to naive with a
    structured warning instead of an error.
    """
    config = config or AnalyticsConfig()
    data = [float(v) for v in values]
    product_id, warehouse_id = _split_ids(series_id)
    profile, candidates, reasons = route_series(list(data), config, season, include_ml, dates)
    if force_model is not None:
        if force_model not in _MODEL_FACTORIES:
            raise ValueError(
                f"Unknown model: {force_model}. Valid: {sorted(_MODEL_FACTORIES)}."
            )
        candidates = [force_model]
        reasons = [f"explicitly requested model: {force_model}"]
    warnings = [reason for reason in reasons if "excluded" in reason or "fallback" in reason]
    comparison = ModelComparison(series_id=series_id, metric=config.comparison_metric)
    fold_counts: dict[str, int] = {}
    wape_means: dict[str, float] = {}
    metric_names = (config.comparison_metric,)
    if config.comparison_metric != "wape":
        # WAPE is tracked alongside for scale-free confidence assessment.
        metric_names = (config.comparison_metric, "wape")
    for model_name in candidates:
        try:
            model = build_model(model_name, season)
            folds = walk_forward(
                np.asarray(data),
                {model_name: model},
                horizon=config.forecast_horizon,
                step=config.validation_step,
                min_history=config.min_history,
                metric_names=metric_names,
                series_id=series_id,
            )
        except InsufficientHistoryError as exc:
            comparison.skipped[model_name] = str(exc)
            continue
        scored = [
            fold.metrics[config.comparison_metric] for fold in folds
            if fold.metrics[config.comparison_metric] is not None
        ]
        if not scored:
            comparison.skipped[model_name] = "Metric undefined on all folds."
            continue
        comparison.scores[model_name] = float(sum(scored) / len(scored))
        fold_counts[model_name] = len(folds)
        wape_values = [fold.metrics.get("wape") for fold in folds
                       if fold.metrics.get("wape") is not None]
        if wape_values:
            wape_means[model_name] = float(sum(wape_values) / len(wape_values))
    fallback_used = False
    if comparison.scores:
        selected = min(comparison.scores, key=lambda k: comparison.scores[k])
    else:
        # Structured fallback: prefer naive, then deterministic zero.
        selected = "naive" if len(data) >= 1 else "zero"
        fallback_used = True
        warnings.append(
            fallback_explanation("no routed candidate validated", selected)
        )
    score = comparison.scores.get(selected)
    folds = fold_counts.get(selected, 0)
    confidence_error = wape_means.get(selected)
    if confidence_error is None and selected == "zero" and score == 0:
        # Perfect deterministic backtest on all-zero history.
        confidence_error = 0.0
    explanation = (
        explain_selection(selected, profile, comparison)
        if not fallback_used
        else fallback_explanation("all routed candidates failed validation", selected)
    )
    confidence = confidence_descriptor(
        folds=folds,
        error=confidence_error,
        volatility=profile.coefficient_of_variation,
        zero_ratio=profile.zero_ratio,
    )
    return SelectionResult(
        series_id=series_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        selected_model=selected,
        fallback_used=fallback_used,
        validation_metric=config.comparison_metric,
        validation_score=score,
        validation_folds=folds,
        demand_profile=profile.profile,
        candidates=candidates,
        skipped=comparison.skipped,
        explanation=explanation,
        confidence=confidence,
        warnings=warnings,
        training_start=training_start,
        training_end=training_end,
        model_config={"season": season, "include_ml": include_ml,
                      "horizon": config.forecast_horizon, "step": config.validation_step,
                      "min_history": config.min_history},
    )
