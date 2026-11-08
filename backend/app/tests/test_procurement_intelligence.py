"""Phase 6 integration tests on a tiny isolated dataset."""

from datetime import date

import pytest

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.datasets import demand as demand_loader
from backend.app.analytics.datasets import inventory as inventory_loader
from backend.app.analytics.datasets import procurement as procurement_loader
from backend.app.analytics.datasets import suppliers as suppliers_loader
from backend.app.analytics.inventory import forecast_inputs
from backend.app.analytics.inventory import reports as intel_reports
from backend.app.analytics.inventory.types import DEFAULT_INVENTORY_CONFIG
from backend.app.analytics.procurement import concentration, inbound, reports
from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG
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
async def test_full_supplier_build_on_tiny_dataset():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        links = await suppliers_loader.load_suppliers(session)
        po_lines = await procurement_loader.load_purchase_orders(session)
        shipments = await procurement_loader.load_shipments(session)
        snapshots = await inventory_loader.load_snapshots(session)
        transactions = await inventory_loader.load_transactions(session)
        demand = await demand_loader.load_demand(session)
        assert not links.empty and not po_lines.empty
        persisted = await forecast_inputs.load_persisted_forecasts(session)
        inputs = forecast_inputs.frame_to_inputs(persisted)
        generated = forecast_inputs.generate_inputs(
            demand, ANALYSIS,
            AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60),
        )
        inputs.update(generated)
        intelligence = []
        for key, forecast in sorted(inputs.items()):
            product_id, warehouse_id = key.split("|")
            intelligence.append(intel_reports.build_intelligence(
                product_id, warehouse_id, snapshots, transactions, demand,
                forecast, shipments, po_lines, ANALYSIS, DEFAULT_INVENTORY_CONFIG,
            ))
        assert len(intelligence) == 4
        supplier_ids = sorted(links["supplier_id"].astype(str).unique().tolist())
        assert len(supplier_ids) == 2
        names = dict(zip(links["supplier_id"].astype(str), links["supplier_name"].astype(str)))
        results = [
            reports.build_supplier_result(
                supplier_id, names[supplier_id], po_lines, shipments, links,
                intelligence, ANALYSIS, DEFAULT_PROCUREMENT_CONFIG,
            )
            for supplier_id in supplier_ids
        ]
        assert len(results) == 2
        for result in results:
            assert result.synthetic is True
            assert result.performance is not None
            assert result.delivery is not None
            assert result.risk_signal is not None
            assert result.exposure is not None
            payload = result.to_dict()
            assert payload["supplier_id"] == result.supplier_id
        report = reports.build_report(
            results, [], concentration.dependency_classes(links), [],
            ANALYSIS, 7, {"start": None, "end": None}, DEFAULT_PROCUREMENT_CONFIG,
        )
        assert "SYNTHETIC" in report["disclaimer"]
        assert len(report["results"]) == 2
        markdown = reports.render_markdown(report)
        assert "SYNTHETIC" in markdown


@pytest.mark.asyncio
async def test_inbound_and_concentration_on_tiny_dataset():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        links = await suppliers_loader.load_suppliers(session)
        po_lines = await procurement_loader.load_purchase_orders(session)
        snapshots = await inventory_loader.load_snapshots(session)
        transactions = await inventory_loader.load_transactions(session)
        demand = await demand_loader.load_demand(session)
        generated = forecast_inputs.generate_inputs(
            demand, ANALYSIS,
            AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60),
        )
        intelligence = []
        for key, forecast in sorted(generated.items()):
            product_id, warehouse_id = key.split("|")
            intelligence.append(intel_reports.build_intelligence(
                product_id, warehouse_id, snapshots, transactions, demand,
                forecast, await procurement_loader.load_shipments(session),
                po_lines, ANALYSIS, DEFAULT_INVENTORY_CONFIG,
            ))
        open_all = []
        for supplier_id in links["supplier_id"].astype(str).unique().tolist():
            result = reports.build_supplier_result(
                supplier_id, supplier_id, po_lines,
                await procurement_loader.load_shipments(session),
                links, intelligence, ANALYSIS, DEFAULT_PROCUREMENT_CONFIG,
            )
            open_all.extend(result.open_orders)
        states = set()
        for item in intelligence:
            coverage = inbound.describe_inbound_coverage(
                item.product_id, item.warehouse_id, item.forecast,
                item.position.current_on_hand if item.position else None,
                open_all, "2026-07-07",
            )
            states.add(coverage.state)
        assert states <= {"INBOUND_SUPPORTED", "INBOUND_PARTIAL", "INBOUND_INSUFFICIENT",
                          "NO_KNOWN_INBOUND", "UNKNOWN"}
        classes = concentration.dependency_classes(links)
        assert sum(len(v) for v in classes.values()) == 4
