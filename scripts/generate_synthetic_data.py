"""CLI for synthetic ERP data generation (Phase 2).

This dataset is synthetic and is generated solely for demonstration,
testing, analytics development, and portfolio purposes.

Examples:
    python scripts/generate_synthetic_data.py generate --seed 42
    python scripts/generate_synthetic_data.py validate
    python scripts/generate_synthetic_data.py report
    python scripts/generate_synthetic_data.py sample
    python scripts/generate_synthetic_data.py reset --reset
"""

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.core.database import AsyncSessionLocal, dispose_engine, run_async
from backend.app.data import SYNTHETIC_DISCLAIMER
from backend.app.data.config import GenerationConfig
from backend.app.data.ingestion.pipeline import (
    DatasetExistsError,
    dataset_exists,
    generate_dataset,
    load_dataset,
    reset_dataset,
)
from backend.app.data.quality.checks import run_all_checks
from backend.app.data.quality.report import (
    build_report,
    export_samples,
    persist_results,
    write_dictionary_files,
)


def _build_config(args: argparse.Namespace) -> GenerationConfig:
    end_date = date.fromisoformat(args.end_date) if args.end_date else date(2026, 6, 30)
    return GenerationConfig(
        seed=args.seed,
        organization_count=args.organization_count,
        product_count=args.product_count,
        supplier_count=args.supplier_count,
        warehouse_count=args.warehouse_count,
        history_days=args.history_days,
        end_date=end_date,
    )


def _add_common(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--seed", type=int, default=42, help="Deterministic random seed.")
    sub.add_argument("--organization-count", type=int, default=1)
    sub.add_argument("--product-count", type=int, default=24)
    sub.add_argument("--supplier-count", type=int, default=8)
    sub.add_argument("--warehouse-count", type=int, default=3)
    sub.add_argument("--history-days", type=int, default=365)
    sub.add_argument("--end-date", type=str, default=None,
                     help="History end date YYYY-MM-DD (default 2026-06-30).")


async def _check_connection() -> bool:
    from sqlalchemy import text

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def _cmd_generate(args: argparse.Namespace) -> int:
    if not await _check_connection():
        print("SupplySense Nexus database is unavailable.")
        print("Verify PostgreSQL is running and DATABASE_URL is configured.")
        return 2
    config = _build_config(args)
    async with AsyncSessionLocal() as session:
        if await dataset_exists(session) and not args.reset:
            print("A synthetic dataset already exists. Re-run with --reset to regenerate.")
            return 1
        if args.reset:
            removed = await reset_dataset(session)
            await session.commit()
            print(f"Reset scoped synthetic tables: {sum(removed.values())} rows removed.")
    generated_at = time.perf_counter()
    dataset = generate_dataset(config)
    generation_seconds = time.perf_counter() - generated_at
    async with AsyncSessionLocal() as session:
        try:
            if args.reset:
                await reset_dataset(session)
            await load_dataset(session, dataset, allow_existing=args.reset)
            await session.commit()
        except DatasetExistsError as exc:
            await session.rollback()
            print(str(exc))
            return 1
        except Exception:
            await session.rollback()
            raise
        ingestion_seconds = time.perf_counter() - generated_at - generation_seconds
        validated_at = time.perf_counter()
        results = await run_all_checks(session, config, dataset)
        await persist_results(session, results, config.batch_size)
        await session.commit()
        validation_seconds = time.perf_counter() - validated_at
        report = await build_report(
            session, config, results,
            {"generation": generation_seconds, "ingestion": ingestion_seconds,
             "validation": validation_seconds},
        )
    await dispose_engine()
    failed = report.quality.get("FAIL", 0)
    print(json.dumps(report.to_dict(), indent=2))
    print(SYNTHETIC_DISCLAIMER)
    return 1 if failed else 0


async def _cmd_validate(_args: argparse.Namespace) -> int:
    from backend.app.data.config import DEFAULT_CONFIG
    from backend.app.data.ingestion.pipeline import GeneratedDataset

    if not await _check_connection():
        print("SupplySense Nexus database is unavailable.")
        return 2
    async with AsyncSessionLocal() as session:
        results = await run_all_checks(session, DEFAULT_CONFIG, GeneratedDataset(config=DEFAULT_CONFIG))
        for result in results:
            print(f"{result.status:4s} [{result.severity:8s}] {result.check_name:32s} "
                  f"{result.table:24s} {result.observed}")
        failed = sum(1 for r in results if r.status == "FAIL")
    await dispose_engine()
    return 1 if failed else 0


async def _cmd_report(_args: argparse.Namespace) -> int:
    from backend.app.data.config import DEFAULT_CONFIG

    if not await _check_connection():
        print("SupplySense Nexus database is unavailable.")
        return 2
    async with AsyncSessionLocal() as session:
        report = await build_report(session, DEFAULT_CONFIG, [])
    await dispose_engine()
    print(json.dumps(report.to_dict(), indent=2))
    print(SYNTHETIC_DISCLAIMER)
    return 0


async def _cmd_sample(args: argparse.Namespace) -> int:
    if not await _check_connection():
        print("SupplySense Nexus database is unavailable.")
        return 2
    async with AsyncSessionLocal() as session:
        paths = await export_samples(session, args.output_dir, args.limit)
        dict_paths = write_dictionary_files(args.dictionary_dir)
    await dispose_engine()
    for path in [*paths, *dict_paths]:
        print(f"Wrote {path}")
    print(SYNTHETIC_DISCLAIMER)
    return 0


async def _cmd_reset(_args: argparse.Namespace) -> int:
    if not await _check_connection():
        print("SupplySense Nexus database is unavailable.")
        return 2
    async with AsyncSessionLocal() as session:
        removed = await reset_dataset(session)
        await session.commit()
    await dispose_engine()
    print(f"Reset scoped synthetic tables: {sum(removed.values())} rows removed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch to the selected subcommand."""
    parser = argparse.ArgumentParser(
        description="Generate deterministic synthetic ERP data for SupplySense Nexus."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate", help="Generate, ingest, validate, and report.")
    _add_common(gen)
    gen.add_argument("--reset", action="store_true",
                     help="Remove only the generated SupplySense dataset first.")
    val = commands.add_parser("validate", help="Run data-quality checks on current data.")
    _add_common(val)
    commands.add_parser("report", help="Print record counts from the database.")
    sample = commands.add_parser("sample", help="Export small CSV samples and dictionary.")
    sample.add_argument("--output-dir", default="data/sample")
    sample.add_argument("--dictionary-dir", default="data/dictionaries")
    sample.add_argument("--limit", type=int, default=200)
    commands.add_parser("reset", help="Remove only the generated SupplySense dataset.")
    args = parser.parse_args(argv)
    if args.command == "generate":
        return run_async(_cmd_generate(args))
    if args.command == "validate":
        return run_async(_cmd_validate(args))
    if args.command == "report":
        return run_async(_cmd_report(args))
    if args.command == "sample":
        return run_async(_cmd_sample(args))
    if args.command == "reset":
        return run_async(_cmd_reset(args))
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
