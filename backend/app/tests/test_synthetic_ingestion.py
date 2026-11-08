"""Phase 2 ingestion tests: batch insert, rollback, idempotency, reset."""

import pytest
from sqlalchemy import func, select

from backend.app.data.config import build_config
from backend.app.data.ingestion.loaders import insert_batch
from backend.app.data.ingestion.pipeline import (
    DatasetExistsError,
    dataset_exists,
    generate_dataset,
    load_dataset,
    reset_dataset,
)
from backend.app.data.quality.checks import run_all_checks
from backend.app.data.quality.report import build_report, persist_results
from backend.app.models import Organization, Product
from backend.app.tests.conftest import TestSessionLocal


def _tiny_config(**overrides):
    base = {"history_days": 14, "product_count": 6, "supplier_count": 3, "warehouse_count": 2}
    base.update(overrides)
    return build_config(**base)


@pytest.mark.asyncio
async def test_successful_ingestion():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        counts = await load_dataset(session, dataset)
        await session.commit()
        assert counts["organizations"] == 1
        assert counts["products"] == 6
        assert counts["demand_observations"] == 6 * 2 * 14
        result = await session.execute(select(func.count(Product.id)))
        assert result.scalar() == 6


@pytest.mark.asyncio
async def test_transaction_rollback_on_bad_record():
    config = _tiny_config()
    dataset = generate_dataset(config)
    before = 0
    async with TestSessionLocal() as session:
        result = await session.execute(select(func.count(Organization.id)))
        before = result.scalar() or 0
        dataset.products[0]["organization_key"] = "NO-SUCH-ORG"
        with pytest.raises(KeyError):
            await load_dataset(session, dataset)
        await session.rollback()
        result = await session.execute(select(func.count(Organization.id)))
        assert (result.scalar() or 0) == before


@pytest.mark.asyncio
async def test_batch_insertion_counts():
    from backend.app.models import ProductCategory

    async with TestSessionLocal() as session:
        objects = [ProductCategory(name=f"Batch Cat {index}") for index in range(120)]
        total = await insert_batch(session, objects, batch_size=25)
        await session.commit()
        assert total == 120
        result = await session.execute(select(func.count(ProductCategory.id)))
        assert result.scalar() == 120


@pytest.mark.asyncio
async def test_duplicate_generation_is_prevented():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        assert await dataset_exists(session)
        with pytest.raises(DatasetExistsError):
            await load_dataset(session, generate_dataset(config))


@pytest.mark.asyncio
async def test_reset_works_safely():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        removed = await reset_dataset(session)
        await session.commit()
        assert removed["organizations"] == 1
        assert removed["products"] == 6
        assert not await dataset_exists(session)
        # Regeneration works after reset.
        await load_dataset(session, generate_dataset(config), allow_existing=True)
        await session.commit()
        assert await dataset_exists(session)


@pytest.mark.asyncio
async def test_quality_checks_pass_on_generated_data():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        results = await run_all_checks(session, config, dataset)
        failed = [r for r in results if r.status == "FAIL"]
        assert failed == [], f"Unexpected failures: {[(r.check_name, r.table) for r in failed]}"
        persisted = await persist_results(session, results, 100)
        await session.commit()
        assert persisted == len(results)
        report = await build_report(session, config, results)
        assert report.counts["organizations"] == 1


def test_reproducibility_same_seed():
    config = _tiny_config()
    first = generate_dataset(config)
    second = generate_dataset(config)
    assert first.demand == second.demand
    assert first.purchase_orders == second.purchase_orders
    assert first.inventory_transactions == second.inventory_transactions
    assert first.table_counts() == second.table_counts()


def test_different_seed_differs():
    first = generate_dataset(_tiny_config(seed=42))
    second = generate_dataset(_tiny_config(seed=43))
    assert first.demand != second.demand
