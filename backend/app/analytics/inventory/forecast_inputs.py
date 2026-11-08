"""Forecast-to-inventory integration (Phase 5).

Consumption order per series:
1. Persisted Phase 4 ``forecasts`` rows (latest origin per model
   version), with full provenance from ``model_versions``.
2. If none exist, the public ``evaluate_dataset`` interface generates
   the selection/forecast on demand (no model classes touched
   directly); provenance is flagged ``generated_for_analysis``.
3. If generation also fails (e.g. insufficient history), an explicit
   MISSING_FORECAST input is returned. Forecasts are never fabricated.

Join key for persisted rows: product_id + warehouse_id + forecast_date.
"""

from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.inventory.types import ForecastInput
from backend.app.models import Forecast, ModelVersion


async def load_persisted_forecasts(
    session: AsyncSession,
    product_ids: list[str] | None = None,
    warehouse_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Load persisted forecast rows with model provenance (column-only)."""
    statement = (
        select(
            Forecast.product_id,
            Forecast.warehouse_id,
            Forecast.forecast_date,
            Forecast.point_estimate,
            Forecast.lower_bound,
            Forecast.upper_bound,
            Forecast.confidence_level,
            Forecast.forecast_horizon_days,
            Forecast.model_version_id,
            ModelVersion.model_name,
            ModelVersion.version,
            ModelVersion.model_type,
            ModelVersion.metrics,
        )
        .join(ModelVersion, ModelVersion.id == Forecast.model_version_id, isouter=True)
    )
    if product_ids:
        statement = statement.where(Forecast.product_id.in_(product_ids))
    if warehouse_ids:
        statement = statement.where(Forecast.warehouse_id.in_(warehouse_ids))
    rows = (await session.execute(statement)).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "product_id", "warehouse_id", "forecast_date", "point", "lower", "upper",
            "confidence_level", "horizon", "model_version_id", "model_name",
            "model_version", "model_type", "model_metrics",
        ],
    )
    if frame.empty:
        return frame
    frame["forecast_date"] = pd.to_datetime(frame["forecast_date"]).dt.date
    for column in ("point", "lower", "upper"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values(["product_id", "warehouse_id", "forecast_date"]).reset_index(drop=True)


def _origin_of(dates: list[date]) -> date:
    return min(dates) - timedelta(days=1)


def frame_to_inputs(frame: pd.DataFrame) -> dict[str, ForecastInput]:
    """Group persisted rows into per-series inputs (latest origin wins)."""
    inputs: dict[str, ForecastInput] = {}
    if frame.empty:
        return inputs
    for (product_id, warehouse_id, version_id), group in frame.groupby(
        ["product_id", "warehouse_id", "model_version_id"]
    ):
        ordered = group.sort_values("forecast_date")
        dates = [d.isoformat() for d in ordered["forecast_date"].tolist()]
        first = ordered.iloc[0]
        key = f"{product_id}|{warehouse_id}"
        candidate = ForecastInput(
            product_id=str(product_id),
            warehouse_id=str(warehouse_id),
            origin=_origin_of(ordered["forecast_date"].tolist()).isoformat(),
            forecast_dates=dates,
            horizon=int(first["horizon"]) if pd.notna(first["horizon"]) else len(dates),
            point=[float(v) for v in ordered["point"].tolist()],
            lower=[float(v) for v in ordered["lower"].tolist()],
            upper=[float(v) for v in ordered["upper"].tolist()],
            confidence_level=float(first["confidence_level"]) if pd.notna(first["confidence_level"]) else 0.95,
            interval_method="empirical_residual_quantile",
            model_name=str(first["model_name"] or ""),
            model_version=str(first["model_version"] or ""),
            source="persisted",
        )
        # Latest origin wins when several versions cover a series.
        current = inputs.get(key)
        if current is None or candidate.origin >= current.origin:
            inputs[key] = candidate
    return inputs


def missing_forecast(product_id: str, warehouse_id: str, origin: str) -> ForecastInput:
    """Build the explicit missing-forecast state (never fabricated)."""
    return ForecastInput(
        product_id=product_id,
        warehouse_id=warehouse_id,
        origin=origin,
        source="persisted",
        missing=True,
    )


def generate_inputs(
    demand_frame: pd.DataFrame,
    origin: date,
    config: AnalyticsConfig,
    season: int = 7,
    include_ml: bool = False,
    max_series: int | None = None,
) -> dict[str, ForecastInput]:
    """Generate forecast inputs via the public Phase 4 report interface.

    Only model selection/forecasting entry points are used
    (``evaluate_dataset``); no forecasting model class is touched.
    """
    # Local import keeps the public-interface boundary explicit.
    from backend.app.analytics.reports.forecasting_report import evaluate_dataset

    series: dict[str, dict[str, Any]] = {}
    for (product_id, warehouse_id), group in demand_frame.groupby(["product_id", "warehouse_id"]):
        ordered = group.sort_values("date")
        series[f"{product_id}|{warehouse_id}"] = {
            "values": [float(v) for v in ordered["quantity"].tolist()],
            "product_id": str(product_id),
            "warehouse_id": str(warehouse_id),
            "training_start": str(ordered["date"].min()),
            "training_end": str(ordered["date"].max()),
        }
    report = evaluate_dataset(
        series, origin, config, season=season, include_ml=include_ml, max_series=max_series
    )
    inputs: dict[str, ForecastInput] = {}
    for evaluation in report["evaluations"]:
        selection = evaluation["selection"]
        forecast = evaluation["forecast"]
        key = selection["series_id"]
        inputs[key] = ForecastInput(
            product_id=selection["product_id"],
            warehouse_id=selection["warehouse_id"],
            origin=forecast["origin"],
            forecast_dates=list(forecast["forecast_dates"]),
            horizon=int(forecast["horizon"]),
            point=[float(v) for v in forecast["point"]],
            lower=[float(v) for v in forecast["lower"]],
            upper=[float(v) for v in forecast["upper"]],
            confidence_level=float(forecast["confidence_level"]),
            interval_method=str(forecast["interval_method"]),
            model_name=str(forecast["model_name"]),
            model_version="4.0.0",
            demand_profile=str(forecast["demand_profile"]),
            validation_metric=str(forecast["validation_metric"]),
            validation_score=forecast["validation_score"],
            validation_folds=int(forecast["validation_folds"]),
            explanation=str(forecast["explanation"]),
            confidence=dict(forecast["confidence"]),
            warnings=list(forecast["warnings"]),
            source="generated_for_analysis",
        )
    return inputs
