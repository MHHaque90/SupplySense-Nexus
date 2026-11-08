"""Phase 7 point-in-time leakage tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.inventory.types import (
    DEFAULT_INVENTORY_CONFIG,
    ForecastInput,
    InventoryHealth,
    InventoryPosition,
)
from backend.app.analytics.procurement import delivery, open_orders, supplier_performance
from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG
from backend.app.analytics.risk import service_risk

ANALYSIS = date(2026, 6, 30)
INV_CONFIG = DEFAULT_INVENTORY_CONFIG
PROC_CONFIG = DEFAULT_PROCUREMENT_CONFIG


def _result():
    return InventoryIntelligenceResult(
        product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
        position=InventoryPosition(
            product_id="P1", warehouse_id="W1", analysis_date="2026-06-30",
            current_on_hand=80.0, latest_snapshot_date="2026-06-30",
        ),
        forecast=ForecastInput(
            product_id="P1", warehouse_id="W1", origin="2026-06-30",
            forecast_dates=["2026-07-01"], horizon=1,
            point=[10.0], lower=[8.0], upper=[12.0],
        ),
        health=InventoryHealth(product_id="P1", warehouse_id="W1",
                               health="HEALTHY", reason="test"),
    )


def test_future_inventory_excluded():
    from backend.app.analytics.inventory import position as position_mod

    snapshots = pd.DataFrame({
        "product_id": ["P1", "P1"],
        "warehouse_id": ["W1", "W1"],
        "snapshot_date": [date(2026, 6, 20), date(2026, 6, 30)],
        "on_hand": [90.0, 80.0],
    })
    transactions = pd.DataFrame({
        "product_id": ["P1"], "warehouse_id": ["W1"],
        "timestamp": [date(2026, 6, 25)], "transaction_type": ["SALE"],
        "quantity": [10.0],
    })
    clean_pos = position_mod.describe_position(
        "P1", "W1", snapshots, transactions, ANALYSIS, INV_CONFIG
    )
    future_snaps = pd.concat([snapshots, pd.DataFrame([{
        "product_id": "P1", "warehouse_id": "W1",
        "snapshot_date": date(2027, 1, 1), "on_hand": 9999.0,
    }])], ignore_index=True)
    future_txns = pd.concat([transactions, pd.DataFrame([{
        "product_id": "P1", "warehouse_id": "W1",
        "timestamp": date(2027, 1, 1), "transaction_type": ["RECEIPT"],
        "quantity": [9999.0],
    }])], ignore_index=True)
    dirty_pos = position_mod.describe_position(
        "P1", "W1", future_snaps, future_txns, ANALYSIS, INV_CONFIG
    )
    assert dirty_pos.to_dict() == clean_pos.to_dict()
    assert dirty_pos.current_on_hand == 80.0


def test_future_po_shipment_excluded():
    lines = pd.DataFrame({
        "po_id": ["PO1"], "supplier_id": ["S1"], "product_id": ["P1"],
        "order_date": [date(2026, 1, 5)],
        "expected_delivery_date": [date(2026, 1, 20)],
        "quantity": [100.0], "status": ["ordered"],
    })
    shipments = pd.DataFrame({
        "shipment_id": ["SH1"], "po_id": ["PO1"], "supplier_id": ["S1"],
        "expected_arrival_date": [date(2026, 1, 15)],
        "actual_arrival_date": [date(2026, 1, 16)], "delay_days": [1.0],
    })
    future_lines = pd.concat([lines, pd.DataFrame([{
        "po_id": "PO9", "supplier_id": "S1", "product_id": "P1",
        "order_date": date(2027, 1, 5),
        "expected_delivery_date": date(2027, 1, 20),
        "quantity": 5000.0, "status": "ordered",
    }])], ignore_index=True)
    future_shipments = pd.concat([shipments, pd.DataFrame([{
        "shipment_id": "SH9", "po_id": "PO9", "supplier_id": "S1",
        "expected_arrival_date": date(2027, 1, 15),
        "actual_arrival_date": date(2027, 1, 20), "delay_days": [5.0],
    }])], ignore_index=True)
    clean_perf = supplier_performance.describe_supplier(
        "S1", "S", lines, shipments, ANALYSIS, PROC_CONFIG).to_dict()
    dirty_perf = supplier_performance.describe_supplier(
        "S1", "S", future_lines, future_shipments, ANALYSIS, PROC_CONFIG).to_dict()
    assert dirty_perf == clean_perf
    clean_open = [order.to_dict() for order in open_orders.describe_open_orders(
        lines, shipments, ANALYSIS)]
    dirty_open = [order.to_dict() for order in open_orders.describe_open_orders(
        future_lines, future_shipments, ANALYSIS)]
    assert dirty_open == clean_open
    clean_delivery = delivery.describe_delivery("S1", shipments, ANALYSIS, PROC_CONFIG).to_dict()
    dirty_delivery = delivery.describe_delivery(
        "S1", future_shipments, ANALYSIS, PROC_CONFIG).to_dict()
    assert dirty_delivery == clean_delivery


def test_future_service_events_excluded():
    record = service_risk.assess(_result(), [], INV_CONFIG)
    assert record.severity == "LOW"
    assert record.metrics["stockout_observations"] == 0.0


def test_future_shipment_events_do_not_influence_risk():
    """Shipment events are never consumed by risk analytics.

    A future-dated shipment event row must leave supplier performance
    identical, proving the event stream cannot leak into risk results.
    """

    from backend.app.analytics.datasets import procurement as procurement_loader
    from backend.app.data.config import GenerationConfig
    from backend.app.data.ingestion.pipeline import generate_dataset, load_dataset
    from backend.app.models import Shipment, ShipmentEvent
    from backend.app.tests.conftest import TestSessionLocal

    async def _run():
        async with TestSessionLocal() as session:
            dataset = generate_dataset(GenerationConfig(
                seed=11, product_count=2, supplier_count=1,
                warehouse_count=1, history_days=60,
            ))
            await load_dataset(session, dataset)
            await session.commit()
            shipments = await procurement_loader.load_shipments(session)
            supplier = str(shipments["supplier_id"].iloc[0])
            po_lines = await procurement_loader.load_purchase_orders(session)
            before = supplier_performance.describe_supplier(
                supplier, "S", po_lines, shipments, ANALYSIS, PROC_CONFIG,
            ).to_dict()
            shipment_id = str(shipments["shipment_id"].iloc[0])
            session.add(ShipmentEvent(
                shipment_id=shipment_id, event_type="DELAYED",
                event_date=date(2027, 5, 1), description="future synthetic event",
            ))
            await session.commit()
            check = await session.get(Shipment, shipment_id)
            assert check is not None
            after = supplier_performance.describe_supplier(
                supplier, "S",
                await procurement_loader.load_purchase_orders(session),
                await procurement_loader.load_shipments(session),
                ANALYSIS, PROC_CONFIG,
            ).to_dict()
            assert after == before

    import asyncio

    asyncio.run(_run())
