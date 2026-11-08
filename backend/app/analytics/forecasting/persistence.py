"""Forecast persistence on the existing schema (Phase 4, no migration).

Reuses ``model_versions`` (registry metadata as JSON in ``metrics``),
``forecast_runs`` (run metadata + validation metrics JSON), and
``forecasts`` (one row per product/warehouse/date with point and
interval bounds, labeled simulated). Duplicate protection: existing
model versions are reused by (name, version); existing forecast rows
for the same (product, warehouse, date, model version) are skipped,
never duplicated.
"""

import json
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from backend.app.analytics.forecasting.result import ForecastOutput, SelectionResult
from backend.app.analytics.forecasting.selection import model_family
from backend.app.core.data_labels import DataSourceLabel
from backend.app.models import Forecast, ForecastRun, ModelVersion, User

FORECAST_VERSION = "4.0.0"

MODEL_NAMES: tuple[str, ...] = (
    "zero", "naive", "seasonal_naive", "moving_average", "drift", "ses",
    "holt", "holt_winters", "autoreg", "croston", "hgb",
)


class PersistenceError(RuntimeError):
    """Raised when persistence preconditions are unmet."""


async def get_registering_user_id(session: AsyncSession) -> str:
    """Return any existing user id for the required registered_by field."""
    result = await session.execute(select(User.id).limit(1))
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise PersistenceError("No users exist; cannot register a model version.")
    return str(user_id)


async def ensure_model_version(
    session: AsyncSession,
    selection: SelectionResult,
    training_start: str,
    training_end: str,
) -> ModelVersion:
    """Fetch or create the registry row for a selection (duplicate-safe)."""
    existing = await session.execute(
        select(ModelVersion)
        .where(
            ModelVersion.model_name == selection.selected_model,
            ModelVersion.version == FORECAST_VERSION,
        )
        .options(
            noload(ModelVersion.forecasts),
            noload(ModelVersion.forecast_runs),
            noload(ModelVersion.registered_by_user),
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return found
    user_id = await get_registering_user_id(session)
    row = ModelVersion(
        model_name=selection.selected_model,
        model_type=model_family(selection.selected_model),
        version=FORECAST_VERSION,
        training_window_start=date.fromisoformat(training_start) if training_start else None,
        training_window_end=date.fromisoformat(training_end) if training_end else None,
        metrics=json.dumps({
            "validation_metric": selection.validation_metric,
            "validation_score": selection.validation_score,
            "validation_folds": selection.validation_folds,
            "demand_profile": selection.demand_profile,
            "candidates": selection.candidates,
            "model_config": selection.model_config,
            "data_source": DataSourceLabel.SIMULATED.value,
        }),
        file_path=None,
        is_active=False,
        registered_by=user_id,
    )
    session.add(row)
    await session.flush()
    return row


async def record_forecast_run(
    session: AsyncSession,
    model_version_id: str,
    selection: SelectionResult,
    training_start: str,
    training_end: str,
) -> ForecastRun:
    """Record one forecast run with validation metrics JSON."""
    row = ForecastRun(
        model_version_id=model_version_id,
        run_timestamp=date.today(),
        training_window_start=date.fromisoformat(training_start) if training_start else None,
        training_window_end=date.fromisoformat(training_end) if training_end else None,
        validation_metrics=json.dumps({
            "metric": selection.validation_metric,
            "score": selection.validation_score,
            "folds": selection.validation_folds,
            "series_id": selection.series_id,
        }),
        data_source_label=DataSourceLabel.SIMULATED.value,
    )
    session.add(row)
    await session.flush()
    return row


async def persist_forecast(
    session: AsyncSession,
    output: ForecastOutput,
    model_version_id: str,
) -> dict[str, int]:
    """Persist forecast rows, skipping already-stored keys.

    Returns ``{"inserted": n, "skipped": m}`` for the
    (product, warehouse, date, model version) key space.
    """
    existing = await session.execute(
        select(Forecast.forecast_date).where(
            Forecast.product_id == output.product_id,
            Forecast.warehouse_id == output.warehouse_id,
            Forecast.model_version_id == model_version_id,
        )
    )
    stored = {str(row[0]) for row in existing.all()}
    inserted = 0
    skipped = 0
    for position in range(output.horizon):
        forecast_date = output.forecast_dates[position]
        if forecast_date in stored:
            skipped += 1
            continue
        session.add(Forecast(
            product_id=output.product_id,
            warehouse_id=output.warehouse_id,
            forecast_date=date.fromisoformat(forecast_date),
            point_estimate=f"{output.point[position]:.2f}",
            lower_bound=f"{output.lower[position]:.2f}",
            upper_bound=f"{output.upper[position]:.2f}",
            model_version_id=model_version_id,
            confidence_level=f"{output.confidence_level:.2f}",
            forecast_horizon_days=output.horizon,
            data_source_label=DataSourceLabel.SIMULATED.value,
        ))
        inserted += 1
    await session.flush()
    return {"inserted": inserted, "skipped": skipped}


async def forecast_row_count(session: AsyncSession) -> int:
    """Return the total persisted forecast row count."""
    result = await session.execute(select(func.count(Forecast.id)))
    return result.scalar() or 0


def summarize_selection_for_run(selection: SelectionResult) -> dict[str, Any]:
    """Project a selection onto run-record metadata."""
    return {
        "model": selection.selected_model,
        "metric": selection.validation_metric,
        "score": selection.validation_score,
        "folds": selection.validation_folds,
        "profile": selection.demand_profile,
    }
