"""Walk-forward (rolling-origin) validation (Phase 3).

Cutoffs advance from ``min_history`` to ``n - horizon`` in ``step``
increments. Each fold trains on ``series[:cutoff]`` and scores
``series[cutoff:cutoff + horizon]``: future observations never enter
training. Models raising :class:`InsufficientHistoryError` are recorded
as skipped, never silently zero-filled.
"""

import numpy as np

from backend.app.analytics.forecasting import baselines, metrics
from backend.app.analytics.forecasting.result import ValidationFold
from backend.app.analytics.types import InsufficientHistoryError, ModelComparison


def walk_forward(
    series: list[float] | np.ndarray,
    models: dict[str, object],
    horizon: int,
    step: int,
    min_history: int,
    metric_names: tuple[str, ...] = ("mae", "rmse", "smape"),
    series_id: str = "",
    cutoff_labels: list[str] | None = None,
) -> list[ValidationFold]:
    """Evaluate models over rolling origins of one series."""
    values = np.asarray(series, dtype=float).ravel()
    total = len(values)
    if horizon < 1 or step < 1 or min_history < 1:
        raise ValueError("horizon, step, and min_history must be positive.")
    if total < min_history + horizon:
        raise InsufficientHistoryError(
            f"Series length {total} < min_history {min_history} + horizon {horizon}."
        )
    folds: list[ValidationFold] = []
    position = 0
    for cutoff in range(min_history, total - horizon + 1, step):
        label = cutoff_labels[position] if cutoff_labels and position < len(cutoff_labels) else str(cutoff)
        train = values[:cutoff]
        actual = [float(v) for v in values[cutoff: cutoff + horizon]]
        for model_name, model in models.items():
            try:
                fitted = model.fit(train)  # type: ignore[attr-defined]
                forecast = fitted.predict(horizon)
            except InsufficientHistoryError:
                continue
            scores: dict[str, float | None] = {}
            for metric_name in metric_names:
                func = metrics.METRICS[metric_name]
                scores[metric_name] = float(func(actual, forecast.predictions))  # type: ignore[operator]
            folds.append(
                ValidationFold(
                    model_name=model_name,
                    series_id=series_id,
                    cutoff=label,
                    horizon=horizon,
                    actuals=actual,
                    predictions=[float(v) for v in forecast.predictions],
                    metrics=scores,
                    train_length=cutoff,
                )
            )
        position += 1
    if not folds:
        raise InsufficientHistoryError("No model produced a fold; history too short.")
    return folds


def default_baselines(season: int = 7, window: int = 7, alpha: float = 0.3) -> dict[str, object]:
    """Build the standard Phase 3 baseline model set."""
    return {
        "naive": baselines.Naive(),
        "seasonal_naive": baselines.SeasonalNaive(season=season),
        "moving_average": baselines.MovingAverage(window=window),
        "drift": baselines.Drift(),
        "ses": baselines.SimpleExponentialSmoothing(alpha=alpha),
    }


def compare_models(
    series: list[float] | np.ndarray,
    horizon: int,
    step: int,
    min_history: int,
    metric: str = "mae",
    series_id: str = "",
    season: int = 7,
) -> ModelComparison:
    """Select the lowest-error model for one series under one metric.

    Wording is deliberately narrow: lowest observed validation error
    for this series under this metric/configuration — never a global
    "best model" claim.
    """
    values = np.asarray(series, dtype=float).ravel()
    comparison = ModelComparison(series_id=series_id, metric=metric)
    for model_name, model in default_baselines(season=season).items():
        try:
            folds = walk_forward(
                values,
                {model_name: model},
                horizon=horizon,
                step=step,
                min_history=min_history,
                metric_names=(metric,),
                series_id=series_id,
            )
        except InsufficientHistoryError as exc:
            comparison.skipped[model_name] = str(exc)
            continue
        scored = [fold.metrics[metric] for fold in folds if fold.metrics[metric] is not None]
        if not scored:
            comparison.skipped[model_name] = "Metric undefined on all folds."
            continue
        comparison.scores[model_name] = float(sum(scored) / len(scored))
    if comparison.scores:
        comparison.selected_model = min(comparison.scores, key=lambda k: comparison.scores[k])
    return comparison
