"""Phase 2 data-quality tests: checks detect issues and pass on clean data."""

import pytest

from backend.app.data.config import build_config
from backend.app.data.generators.bom import BOMCycleError, validate_no_cycles
from backend.app.data.ingestion.pipeline import generate_dataset, load_dataset
from backend.app.data.quality.checks import (
    check_bom_acyclic,
    check_expected_ranges,
    check_inventory_reconciliation,
    check_procurement_reconciliation,
    check_provenance,
    check_referential_integrity,
    check_temporal_consistency,
    check_uniqueness,
    run_all_checks,
)
from backend.app.data.quality.report import data_dictionary, export_samples, write_dictionary_files
from backend.app.tests.conftest import TestSessionLocal


def _tiny_config(**overrides):
    base = {"history_days": 14, "product_count": 6, "supplier_count": 3, "warehouse_count": 2}
    base.update(overrides)
    return build_config(**base)


@pytest.mark.asyncio
async def test_foreign_key_validation_passes():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        for result in await check_referential_integrity(session):
            assert result.status == "PASS", f"{result.check_name} on {result.table}"


@pytest.mark.asyncio
async def test_uniqueness_and_provenance_pass():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        for result in [*await check_uniqueness(session), *await check_provenance(session)]:
            assert result.status == "PASS", f"{result.check_name} on {result.table}"


@pytest.mark.asyncio
async def test_temporal_consistency_passes():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        for result in await check_temporal_consistency(session, config):
            assert result.status == "PASS", f"{result.check_name}: {result.details}"


@pytest.mark.asyncio
async def test_bom_cycle_detection():
    with pytest.raises(BOMCycleError):
        validate_no_cycles({"X": ["Y"], "Y": ["X"]})
    config = _tiny_config(product_count=8)
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        results = await check_bom_acyclic(session)
        assert all(r.status == "PASS" for r in results)


@pytest.mark.asyncio
async def test_inventory_reconciliation_passes():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        results = await check_inventory_reconciliation(session, dataset)
        assert all(r.status == "PASS" for r in results)


@pytest.mark.asyncio
async def test_procurement_reconciliation_passes():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        results = await check_procurement_reconciliation(session)
        assert all(r.status == "PASS" for r in results)


@pytest.mark.asyncio
async def test_expected_ranges_pass():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        results = await check_expected_ranges(session, dataset)
        assert all(r.status == "PASS" for r in results)


@pytest.mark.asyncio
async def test_full_check_suite_has_no_failures():
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        results = await run_all_checks(session, config, dataset)
        assert results, "Expected check results"
        assert not [r for r in results if r.status == "FAIL"]
        assert all(r.severity in ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL") for r in results)


@pytest.mark.asyncio
async def test_sample_export_and_dictionary(tmp_path):
    config = _tiny_config()
    dataset = generate_dataset(config)
    async with TestSessionLocal() as session:
        await load_dataset(session, dataset)
        await session.commit()
        paths = await export_samples(session, tmp_path / "sample", limit=10)
        assert len(paths) == 5
        dictionary = data_dictionary()
        assert dictionary["fields"], "Dictionary must document fields"
        assert "synthetic" in dictionary["disclaimer"].lower()
        dict_paths = write_dictionary_files(tmp_path / "dictionaries")
        assert len(dict_paths) == 2
