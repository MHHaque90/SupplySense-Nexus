"""Multi-series forecasting evaluation report (Phase 4).

Evaluates routed candidates per series, fits the selected model on
full history, builds empirical intervals from walk-forward residuals,
and aggregates routing, fallback, coverage, and usage statistics.
"""

from datetime import date, timedelta
from typing import Any

import numpy as np

from backend.app.analytics import SYNTHETIC_ANALYTICS_DISCLAIMER
from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.forecasting import intervals as interval_mod
from backend.app.analytics.forecasting.result import ForecastOutput
from backend.app.analytics.forecasting.selection import build_model, select_model
from backend.app.analytics.forecasting.validation import walk_forward

REPORT_LIMITATIONS = [
    "SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.",
    "Forecasts describe synthetic generated demand under this configuration.",
    "Intervals are empirical backtest dispersion, not guarantees.",
    "Empirical coverage on synthetic data does not imply future real-world coverage.",
    "Model comparison is descriptive and configuration-specific; no global winner is claimed.",
]


def _forecast_dates(origin: date, horizon: int) -> list[str]:
    return [(origin + timedelta(days=step)).isoformat() for step in range(1, horizon + 1)]


def evaluate_one_series(
    values: list[float],
    series_id: str,
    product_id: str,
    warehouse_id: str,
    origin: date,
    config: AnalyticsConfig,
    season: int = 7,
    include_ml: bool = False,
    level: float = 0.95,
    training_start: str = "",
    training_end: str = "",
    force_model: str | None = None,
    dates: object | None = None,
) -> dict[str, Any]:
    """Select, refit, forecast, and bound one series."""
    selection = select_model(
        values, series_id, config, season, include_ml, training_start,
        training_end, force_model, dates,
    )
    model = build_model(selection.selected_model, season)
    model.fit(np.asarray(values, dtype=float))
    raw = [float(v) for v in model.predict(config.forecast_horizon).predictions]
    point = [max(0.0, value) for value in raw]
    folds = walk_forward(
        np.asarray(values, dtype=float),
        {selection.selected_model: build_model(selection.selected_model, season)},
        horizon=config.forecast_horizon,
        step=config.validation_step,
        min_history=config.min_history,
        metric_names=("mae",),
        series_id=series_id,
    )
    residuals = interval_mod.collect_residuals(folds, selection.selected_model)
    interval = interval_mod.build_intervals(point, residuals, level)
    output = ForecastOutput(
        series_id=series_id,
        product_id=product_id,
        warehouse_id=warehouse_id,
        origin=origin.isoformat(),
        forecast_dates=_forecast_dates(origin, config.forecast_horizon),
        horizon=config.forecast_horizon,
        model_name=selection.selected_model,
        point=point,
        lower=interval.lower,
        upper=interval.upper,
        confidence_level=level,
        interval_method=interval.method,
        demand_profile=selection.demand_profile,
        validation_metric=selection.validation_metric,
        validation_score=selection.validation_score,
        validation_folds=selection.validation_folds,
        training_start=training_start,
        training_end=training_end,
        model_config=selection.model_config,
        synthetic=True,
        assumptions=[
            "Daily demand series with full calendar continuity.",
            "Validation residuals represent future uncertainty.",
            "Demand is non-negative; point forecasts floored at zero.",
        ],
        warnings=list(selection.warnings),
        explanation=selection.explanation,
        confidence=selection.confidence,
    )
    return {"selection": selection.to_dict(), "forecast": output.to_dict()}


def evaluate_dataset(
    series: dict[str, dict[str, Any]],
    origin: date,
    config: AnalyticsConfig,
    season: int = 7,
    include_ml: bool = False,
    level: float = 0.95,
    max_series: int | None = None,
) -> dict[str, Any]:
    """Evaluate many series; aggregate routing, coverage, and usage.

    Args:
        series: Mapping series_id -> {"values": [...], "product_id": ...,
            "warehouse_id": ..., "training_start": ..., "training_end": ...}.
    """
    items = list(series.items())
    if max_series is not None:
        items = items[:max_series]
    evaluations: list[dict[str, Any]] = []
    for series_id, payload in items:
        evaluations.append(evaluate_one_series(
            [float(v) for v in payload["values"]],
            series_id,
            str(payload.get("product_id", "")),
            str(payload.get("warehouse_id", "")),
            origin,
            config,
            season,
            include_ml,
            level,
            str(payload.get("training_start", "")),
            str(payload.get("training_end", "")),
        ))
    usage: dict[str, int] = {}
    fallbacks = 0
    insufficient = 0
    scores: list[float] = []
    for evaluation in evaluations:
        selection = evaluation["selection"]
        usage[selection["selected_model"]] = usage.get(selection["selected_model"], 0) + 1
        if selection["fallback_used"]:
            fallbacks += 1
        if not selection["candidates"]:
            insufficient += 1
        if selection["validation_score"] is not None:
            scores.append(selection["validation_score"])
    # Mean interval width is the honest aggregate: per-fold coverage is
    # available inside each forecast payload, not as a global number.
    widths = [
        sum(np.subtract(e["forecast"]["upper"], e["forecast"]["lower"])) / e["forecast"]["horizon"]
        for e in evaluations if e["forecast"]["horizon"]
    ]
    return {
        "disclaimer": SYNTHETIC_ANALYTICS_DISCLAIMER,
        "synthetic": True,
        "origin": origin.isoformat(),
        "horizon": config.forecast_horizon,
        "validation_config": config.to_dict(),
        "series_evaluated": len(evaluations),
        "model_usage": usage,
        "fallback_count": fallbacks,
        "insufficient_history_count": insufficient,
        "mean_validation_score": float(np.mean(scores)) if scores else None,
        "median_validation_score": float(np.median(scores)) if scores else None,
        "mean_interval_width": float(np.mean(widths)) if widths else None,
        "metric": config.comparison_metric,
        "evaluations": evaluations,
        "limitations": REPORT_LIMITATIONS,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render the forecasting report as Markdown."""
    lines = [
        "# SupplySense Nexus Forecasting Report",
        "",
        f"_{report['disclaimer']}_",
        "",
        f"Origin: {report['origin']}, horizon: {report['horizon']} days, "
        f"series evaluated: {report['series_evaluated']}",
        "",
        "## Model routing summary (synthetic dataset)",
    ]
    for model, count in sorted(report["model_usage"].items()):
        lines.append(f"- {model}: {count} series")
    lines.append("")
    lines.append(
        f"Fallbacks: {report['fallback_count']}; "
        f"insufficient-history series: {report['insufficient_history_count']}"
    )
    lines.append(
        f"Mean validation {report['metric']}: {report['mean_validation_score']}; "
        f"median: {report['median_validation_score']}"
    )
    lines.append(f"Mean interval width: {report['mean_interval_width']}")
    lines.append("")
    lines.append("## Per-series selections (synthetic dataset)")
    for evaluation in report["evaluations"][:25]:
        selection = evaluation["selection"]
        lines.append(
            f"- {selection['series_id']}: profile={selection['demand_profile']}, "
            f"model={selection['selected_model']}, "
            f"{selection['validation_metric']}={selection['validation_score']}"
        )
    if len(report["evaluations"]) > 25:
        lines.append(f"- ... and {len(report['evaluations']) - 25} more series")
    lines.append("")
    lines.append("## Limitations")
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    return "\n".join(lines) + "\n"
