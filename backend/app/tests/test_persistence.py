"""Phase 4 persistence tests (isolated test database)."""


import pytest
from sqlalchemy import select

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.forecasting import persistence as persistence_mod
from backend.app.analytics.forecasting.result import ForecastOutput
from backend.app.analytics.forecasting.selection import select_model
from backend.app.analytics.reports.forecasting_report import evaluate_one_series
from backend.app.data.config import GenerationConfig
from backend.app.data.ingestion.pipeline import generate_dataset, load_dataset
from backend.app.models import Forecast
from backend.app.tests.conftest import TestSessionLocal


async def _load_tiny(session):
    config = GenerationConfig(
        seed=7, product_count=4, supplier_count=2, warehouse_count=1, history_days=120
    )
    dataset = generate_dataset(config)
    await load_dataset(session, dataset)
    await session.commit()
    return dataset


def _selection():
    values = [10.0 + (i % 7) for i in range(120)]
    return select_model(
        values, "P|W", AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60),
        training_start="2025-01-01", training_end="2025-04-30",
    )


@pytest.mark.asyncio
async def test_model_version_creation_and_reuse():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        selection = _selection()
        first = await persistence_mod.ensure_model_version(
            session, selection, "2025-01-01", "2025-04-30"
        )
        await session.commit()
        assert first.model_type in ("baseline", "statistical", "ml", "intermittent", "ensemble")
        assert first.version == "4.0.0"
        assert first.is_active is False
        second = await persistence_mod.ensure_model_version(
            session, selection, "2025-01-01", "2025-04-30"
        )
        assert second.id == first.id, "Duplicate versions must be reused, not recreated"


@pytest.mark.asyncio
async def test_forecast_persistence_and_duplicate_protection():
    from backend.app.analytics.datasets import demand as demand_loader

    async with TestSessionLocal() as session:
        await _load_tiny(session)
        frame = await demand_loader.load_demand(session)
        group = frame.groupby(["product_id", "warehouse_id"])
        (product_id, warehouse_id), subset = next(iter(group))
        ordered = subset.sort_values("date")
        values = [float(v) for v in ordered["quantity"].tolist()]
        origin = ordered["date"].max()
        evaluation = evaluate_one_series(
            values, f"{product_id}|{warehouse_id}", str(product_id), str(warehouse_id),
            origin, AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60),
        )
        sel = evaluation["selection"]
        from backend.app.analytics.forecasting.result import SelectionResult

        selection = SelectionResult(**{
            key: sel[key] for key in SelectionResult.__dataclass_fields__ if key in sel
        })
        version = await persistence_mod.ensure_model_version(
            session, selection, str(ordered["date"].min()), str(origin)
        )
        run = await persistence_mod.record_forecast_run(
            session, version.id, selection, str(ordered["date"].min()), str(origin)
        )
        assert run.model_version_id == version.id
        payload = evaluation["forecast"]
        output = ForecastOutput(**{
            key: payload[key] for key in ForecastOutput.__dataclass_fields__ if key in payload
        })
        first = await persistence_mod.persist_forecast(session, output, version.id)
        await session.commit()
        assert first["inserted"] == 7 and first["skipped"] == 0
        second = await persistence_mod.persist_forecast(session, output, version.id)
        await session.commit()
        assert second == {"inserted": 0, "skipped": 7}
        rows = (await session.execute(
            select(Forecast).where(Forecast.model_version_id == version.id)
        )).scalars().all()
        assert len(rows) == 7
        assert all(r.data_source_label == "simulated" for r in rows)
        assert all(r.product_id == product_id and r.warehouse_id == warehouse_id for r in rows)
        assert float(rows[0].lower_bound) <= float(rows[0].point_estimate) <= float(rows[0].upper_bound)


@pytest.mark.asyncio
async def test_persistence_requires_users():
    from backend.app.models import Organization

    async with TestSessionLocal() as session:
        session.add(Organization(name="Lonely Org"))
        await session.commit()
        with pytest.raises(persistence_mod.PersistenceError):
            await persistence_mod.get_registering_user_id(session)


def test_forecast_row_count_helper_signature():
    import inspect

    assert "session" in inspect.signature(persistence_mod.forecast_row_count).parameters
