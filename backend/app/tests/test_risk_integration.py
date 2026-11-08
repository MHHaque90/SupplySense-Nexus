"""Phase 7 integration tests on a tiny isolated dataset."""

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
from backend.app.analytics.procurement import concentration as concentration_mod
from backend.app.analytics.procurement import inbound as inbound_mod
from backend.app.analytics.procurement import reports as procurement_reports
from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG
from backend.app.analytics.risk import register as risk_register
from backend.app.analytics.risk import reports as risk_reports
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG
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
async def test_end_to_end_risk_register():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        links = await suppliers_loader.load_suppliers(session)
        po_lines = await procurement_loader.load_purchase_orders(session)
        shipments = await procurement_loader.load_shipments(session)
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
                forecast, shipments, po_lines, ANALYSIS, DEFAULT_INVENTORY_CONFIG,
            ))
        assert len(intelligence) == 4
        supplier_ids = sorted(links["supplier_id"].astype(str).unique().tolist())
        names = dict(zip(links["supplier_id"].astype(str),
                         links["supplier_name"].astype(str)))
        supplier_results = [
            procurement_reports.build_supplier_result(
                supplier_id, names[supplier_id], po_lines, shipments, links,
                intelligence, ANALYSIS, DEFAULT_PROCUREMENT_CONFIG,
            )
            for supplier_id in supplier_ids
        ]
        open_all = [order for result in supplier_results for order in result.open_orders]
        horizon_end = "2026-07-07"
        records = []
        for item in intelligence:
            coverage_in = inbound_mod.describe_inbound_coverage(
                item.product_id, item.warehouse_id, item.forecast,
                item.position.current_on_hand if item.position else None,
                open_all, horizon_end,
            )
            records.extend(risk_reports.build_series_records(
                item, coverage_in, DEFAULT_RISK_CONFIG
            ))
        for result in supplier_results:
            records.extend(risk_reports.build_supplier_records(
                result, links, po_lines, shipments, ANALYSIS, DEFAULT_RISK_CONFIG
            ))
        concentration_rows = list(concentration_mod.volume_shares(po_lines, "spend"))
        records.extend(risk_reports.build_structural_records(
            links, snapshots, intelligence, concentration_rows,
            ANALYSIS, DEFAULT_RISK_CONFIG,
        ))
        assert records, "Register must not be empty"
        domains = {record.domain for record in records}
        assert {"inventory", "uncertainty", "inbound", "service", "overall"} <= domains
        assert "supplier" in domains and "procurement" in domains
        assert "dependency" in domains and "leadtime" in domains
        assert all(record.synthetic is True for record in records)
        assert all(record.analysis_date == "2026-06-30" for record in records)
        for record in records:
            payload = record.to_dict()
            assert payload["risk_id"] and payload["evidence"] is not None
        report = risk_reports.build_report(
            records, ANALYSIS, 7, {"start": None, "end": None}, DEFAULT_RISK_CONFIG
        )
        assert "SYNTHETIC" in report["disclaimer"]
        assert report["risk_overview"]["records"] == len(records)
        markdown = risk_reports.render_markdown(report)
        assert "SYNTHETIC" in markdown


@pytest.mark.asyncio
async def test_register_filters_and_traceability():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        snapshots = await inventory_loader.load_snapshots(session)
        transactions = await inventory_loader.load_transactions(session)
        demand = await demand_loader.load_demand(session)
        shipments = await procurement_loader.load_shipments(session)
        po_lines = await procurement_loader.load_purchase_orders(session)
        generated = forecast_inputs.generate_inputs(
            demand, ANALYSIS,
            AnalyticsConfig(forecast_horizon=7, validation_step=21, min_history=60),
        )
        intelligence = []
        for key, forecast in sorted(generated.items()):
            product_id, warehouse_id = key.split("|")
            intelligence.append(intel_reports.build_intelligence(
                product_id, warehouse_id, snapshots, transactions, demand,
                forecast, shipments, po_lines, ANALYSIS, DEFAULT_INVENTORY_CONFIG,
            ))
        records = []
        for item in intelligence:
            coverage_in = inbound_mod.describe_inbound_coverage(
                item.product_id, item.warehouse_id, item.forecast,
                item.position.current_on_hand if item.position else None,
                [], "2026-07-07",
            )
            records.extend(risk_reports.build_series_records(
                item, coverage_in, DEFAULT_RISK_CONFIG
            ))
        assert risk_register.filter_records(records, domain="inventory")
        assert risk_register.filter_records(
            records, product_id=intelligence[0].product_id
        )
        for record in risk_register.filter_records(records, domain="overall"):
            assert record.supporting_records, "Overall records must cite components"
            assert record.provenance.get("data_source") == "synthetic"
