"""Phase 5 integration tests on a tiny isolated dataset."""

from datetime import date

import pandas as pd
import pytest

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.datasets import demand as demand_loader
from backend.app.analytics.datasets import inventory as inventory_loader
from backend.app.analytics.datasets import procurement as procurement_loader
from backend.app.analytics.inventory import forecast_inputs, reports
from backend.app.analytics.inventory.types import DEFAULT_INVENTORY_CONFIG
from backend.app.data.config import GenerationConfig
from backend.app.data.ingestion.pipeline import generate_dataset, load_dataset
from backend.app.tests.conftest import TestSessionLocal

ANALYSIS = date(2026, 6, 30)


async def _load_tiny(session):
    config = GenerationConfig(
        seed=11, product_count=4, supplier_count=2, warehouse_count=1, history_days=120
    )
    dataset = generate_dataset(config)
    await load_dataset(session, dataset)
    await session.commit()


@pytest.mark.asyncio
async def test_persisted_first_then_generated_fallback():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        persisted = await forecast_inputs.load_persisted_forecasts(session)
        assert persisted.empty  # nothing persisted in a fresh tiny dataset
        demand = await demand_loader.load_demand(session)
        generated = forecast_inputs.generate_inputs(
            demand, ANALYSIS,
            AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60),
        )
        assert len(generated) == 4  # 4 products x 1 warehouse
        for key, result in generated.items():
            assert result.source == "generated_for_analysis"
            assert not result.missing
            assert len(result.point) == 7


@pytest.mark.asyncio
async def test_full_intelligence_on_tiny_dataset():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        snapshots = await inventory_loader.load_snapshots(session)
        transactions = await inventory_loader.load_transactions(session)
        demand = await demand_loader.load_demand(session)
        shipments = await procurement_loader.load_shipments(session)
        orders = await procurement_loader.load_purchase_orders(session)
        generated = forecast_inputs.generate_inputs(
            demand, ANALYSIS,
            AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60),
        )
        results = []
        for key, forecast in sorted(generated.items()):
            product_id, warehouse_id = key.split("|")
            results.append(reports.build_intelligence(
                product_id, warehouse_id, snapshots, transactions, demand,
                forecast, shipments, orders, ANALYSIS, DEFAULT_INVENTORY_CONFIG,
            ))
        assert len(results) == 4
        assert all(result.synthetic is True for result in results)
        assert all(result.health is not None for result in results)
        assert all(result.reorder is not None for result in results)
        assert all(result.coverage is not None for result in results)
        assert all(len(result.trajectory) == 7 for result in results)
        report = reports.build_report(
            results, [], [], [], {"by_warehouse": [], "by_product": []},
            ANALYSIS, 7, DEFAULT_INVENTORY_CONFIG,
        )
        assert report["summary"]["series"] == 4
        assert sum(report["summary"]["health"].values()) == 4
        markdown = reports.render_markdown(report)
        assert "SYNTHETIC DATA" in markdown


@pytest.mark.asyncio
async def test_missing_forecast_yields_unknown_states():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        snapshots = await inventory_loader.load_snapshots(session)
        transactions = await inventory_loader.load_transactions(session)
        demand = await inventory_loader.load_snapshots(session)
        missing = forecast_inputs.missing_forecast("P1", "W1", "2026-06-30")
        result = reports.build_intelligence(
            "P1", "W1", snapshots, transactions, demand, missing,
            pd.DataFrame(), pd.DataFrame(), ANALYSIS, DEFAULT_INVENTORY_CONFIG,
        )
        assert result.trajectory == []
        assert result.coverage.forecast_days_of_supply_state == "unknown"
        assert result.stockout.exposure == "unknown"
        assert result.health.health in ("UNKNOWN", "STOCKOUT")
        assert any("No forecast" in warning for warning in result.warnings)
