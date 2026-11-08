"""Phase 3 dataset loader tests (isolated test database)."""

from datetime import date

import pytest

from backend.app.analytics.datasets import demand as demand_ds
from backend.app.analytics.datasets import inventory as inventory_ds
from backend.app.analytics.datasets import procurement as procurement_ds
from backend.app.analytics.datasets import sales as sales_ds
from backend.app.analytics.datasets import suppliers as suppliers_ds
from backend.app.data.config import GenerationConfig
from backend.app.data.ingestion.pipeline import generate_dataset, load_dataset
from backend.app.tests.conftest import TestSessionLocal


async def _load_tiny(session):
    config = GenerationConfig(
        seed=7, product_count=6, supplier_count=3, warehouse_count=2, history_days=60
    )
    dataset = generate_dataset(config)
    await load_dataset(session, dataset)
    await session.commit()
    return config


@pytest.mark.asyncio
async def test_demand_extraction_columns_and_dtypes():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        frame = await demand_ds.load_demand(session)
        assert list(frame.columns) == demand_ds.DEMAND_COLUMNS
        assert len(frame) == 6 * 2 * 60
        assert frame["quantity"].dtype == float
        assert frame["quantity"].min() >= 0


@pytest.mark.asyncio
async def test_demand_date_and_dimension_filters():
    async with TestSessionLocal() as session:
        config = await _load_tiny(session)
        mid = date.fromordinal(config.start_date.toordinal() + 30)
        frame = await demand_ds.load_demand(session, start=mid, end=mid)
        assert set(frame["date"].unique()) == {mid}
        product = frame["product_id"].iloc[0]
        filtered = await demand_ds.load_demand(session, product_ids=[product])
        assert set(filtered["product_id"].unique()) == {product}
        assert len(filtered) == 2 * 60


@pytest.mark.asyncio
async def test_demand_aggregation_grains():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        frame = await demand_ds.load_demand(session)
        daily = demand_ds.aggregate_demand(frame, "day")
        weekly = demand_ds.aggregate_demand(frame, "week")
        monthly = demand_ds.aggregate_demand(frame, "month")
        assert daily["quantity"].sum() == weekly["quantity"].sum() == monthly["quantity"].sum()
        assert len(weekly) < len(daily)
        assert len(monthly) <= len(weekly)
        with pytest.raises(ValueError):
            demand_ds.aggregate_demand(frame, "fortnight")


@pytest.mark.asyncio
async def test_inventory_and_procurement_extraction():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        snapshots = await inventory_ds.load_snapshots(session)
        transactions = await inventory_ds.load_transactions(session)
        orders = await procurement_ds.load_purchase_orders(session)
        shipments = await procurement_ds.load_shipments(session)
        assert not snapshots.empty and (snapshots["on_hand"] >= 0).all()
        assert set(transactions["transaction_type"].unique()) <= {
            "OPENING_BALANCE", "RECEIPT", "SALE", "ADJUSTMENT",
            "TRANSFER_IN", "TRANSFER_OUT", "RETURN",
        }
        assert not orders.empty and (orders["quantity"] >= orders["moq"].fillna(0)).all()
        assert not shipments.empty and "delay_days" in shipments.columns


@pytest.mark.asyncio
async def test_sales_and_supplier_extraction():
    async with TestSessionLocal() as session:
        await _load_tiny(session)
        orders = await sales_ds.load_sales_orders(session)
        lines = await sales_ds.load_sales_lines(session)
        suppliers = await suppliers_ds.load_suppliers(session)
        assert not orders.empty and not lines.empty
        assert set(lines["order_id"].unique()) <= set(orders["order_id"].unique())
        assert not suppliers.empty and (suppliers["lead_time_days"] >= 0).all()


@pytest.mark.asyncio
async def test_empty_dataset_returns_empty_frames():
    async with TestSessionLocal() as session:
        frame = await demand_ds.load_demand(session)
        assert frame.empty
        assert list(frame.columns) == demand_ds.DEMAND_COLUMNS
        assert (await inventory_ds.load_snapshots(session)).empty
        assert (await procurement_ds.load_purchase_orders(session)).empty
