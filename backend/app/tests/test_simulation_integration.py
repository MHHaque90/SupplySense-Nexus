"""Phase 8 integration tests on a tiny isolated dataset."""

from datetime import date

import pytest

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.datasets import demand as demand_loader
from backend.app.analytics.datasets import inventory as inventory_loader
from backend.app.analytics.datasets import procurement as procurement_loader
from backend.app.analytics.datasets import suppliers as suppliers_loader
from backend.app.analytics.inventory import forecast_inputs
from backend.app.analytics.simulation import events as events_mod
from backend.app.analytics.simulation import reports as sim_reports
from backend.app.analytics.simulation import runner as runner_mod
from backend.app.analytics.simulation import scenarios as scenarios_mod
from backend.app.analytics.simulation import targets as targets_mod
from backend.app.analytics.simulation.types import DEFAULT_SIMULATION_CONFIG
from backend.app.data.config import GenerationConfig
from backend.app.data.ingestion.pipeline import generate_dataset, load_dataset
from backend.app.tests.conftest import TestSessionLocal

ANALYSIS = date(2026, 6, 30)


async def _load_tiny(session):
    dataset = generate_dataset(GenerationConfig(
        seed=11, product_count=4, supplier_count=2, warehouse_count=1, history_days=120,
    ))
    await load_dataset(session, dataset)
    await session.commit()


@pytest.mark.asyncio
async def test_end_to_end_supplier_outage():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        links = await suppliers_loader.load_suppliers(session)
        po_lines = await procurement_loader.load_purchase_orders(session)
        shipments = await procurement_loader.load_shipments(session)
        snapshots = await inventory_loader.load_snapshots(session)
        demand = await demand_loader.load_demand(session)
        supplier_id = str(links["supplier_id"].iloc[0])
        event = events_mod.apply_template("SUPPLIER_OUTAGE", "E1")
        event.affected_suppliers = [supplier_id]
        events_mod.validate_event(event)
        scenario = scenarios_mod.build_scenario(
            scenario_id="S1", event=event, analysis_date="2026-06-30",
            horizon_days=14, simulation_count=1,
            affected_entities=targets_mod.resolve_supplier_products(supplier_id, links),
        )
        persisted = await forecast_inputs.load_persisted_forecasts(session)
        inputs = forecast_inputs.frame_to_inputs(persisted)
        generated = forecast_inputs.generate_inputs(
            demand, ANALYSIS,
            AnalyticsConfig(forecast_horizon=14, validation_step=7, min_history=60),
        )
        inputs.update(generated)
        forecast_by_series = {key: value for key, value in inputs.items()}
        result = runner_mod.run_scenario(
            scenario, forecast_by_series, snapshots, shipments, po_lines,
            links, ANALYSIS, DEFAULT_SIMULATION_CONFIG,
        )
        assert result["per_entity"], "Expected affected series"
        assert result["scenario"].stockout_probability is not None
        assert result["baseline"].stockout_probability is not None
        assert set(result["deltas"]) == {
            "delta_stockout_probability", "delta_unmet_demand",
            "delta_min_inventory", "delta_ending_inventory",
            "delta_stockout_days", "delta_service_exposure",
        }
        assert result["traces"] and result["traces"][0]["scenario_id"] == "S1"
        assert result["traces"][0]["data_source_label"] == "simulated"
        report = sim_reports.build_report(
            scenario, result["baseline"], result["scenario"], result["deltas"],
            result["traces"], DEFAULT_SIMULATION_CONFIG.to_dict(),
        )
        assert "SYNTHETIC" in report["disclaimer"]
        assert "SYNTHETIC" in sim_reports.render_markdown(report)


@pytest.mark.asyncio
async def test_end_to_end_monte_carlo_demand_spike():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        links = await suppliers_loader.load_suppliers(session)
        po_lines = await procurement_loader.load_purchase_orders(session)
        shipments = await procurement_loader.load_shipments(session)
        snapshots = await inventory_loader.load_snapshots(session)
        demand = await demand_loader.load_demand(session)
        event = events_mod.apply_template(
            "DEMAND_SPIKE", "E2", **{"demand_multiplier": 1.5, "duration_days": 7}
        )
        real_product = str(snapshots["product_id"].iloc[0])
        scenario = scenarios_mod.build_scenario(
            scenario_id="S2", event=event, analysis_date="2026-06-30",
            horizon_days=7, simulation_count=30, random_seed=9,
            affected_entities=targets_mod.resolve_explicit(product_ids=[real_product]),
        )
        persisted = await forecast_inputs.load_persisted_forecasts(session)
        inputs = forecast_inputs.frame_to_inputs(persisted)
        generated = forecast_inputs.generate_inputs(
            demand, ANALYSIS,
            AnalyticsConfig(forecast_horizon=7, validation_step=7, min_history=60),
        )
        inputs.update(generated)
        result = runner_mod.run_scenario(
            scenario, inputs, snapshots, shipments, po_lines,
            links, ANALYSIS, DEFAULT_SIMULATION_CONFIG,
        )
        assert result["scenario"].distributions.get("unmet_demand", {}).get("p90") is not None
        assert result["scenario"].distributions.get("unmet_demand", {}).get("p99") is None
        # Reproducibility: same seed regenerates the same scenario outcome.
        again = runner_mod.run_scenario(
            scenario, inputs, snapshots, shipments, po_lines,
            links, ANALYSIS, DEFAULT_SIMULATION_CONFIG,
        )
        assert again["scenario"].to_dict() == result["scenario"].to_dict()
