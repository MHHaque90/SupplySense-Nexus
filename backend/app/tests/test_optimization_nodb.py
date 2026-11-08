"""Phase 10 no-database-access tests (spec section 25.H).

The Optimization Engine operates entirely on in-memory payloads passed
by its caller. No optimization module may import the database stack,
open a session, or embed raw SQL.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import backend.app.analytics.optimization as optimization_package
from backend.app.analytics.optimization import run_optimization

FORBIDDEN_IMPORTS = (
    "sqlalchemy",
    "psycopg",
    "backend.app.core",
    "create_engine",
    "AsyncSessionLocal",
)

RAW_SQL = re.compile(
    r"\bINSERT INTO\b|\bDELETE FROM\b|\bCREATE TABLE\b|\bDROP TABLE\b"
    r"|\bALTER TABLE\b",
    re.IGNORECASE,
)


def _optimization_sources():
    root = Path(optimization_package.__file__).parent
    return sorted(root.glob("*.py"))


def test_optimization_sources_never_reference_the_database_stack():
    assert _optimization_sources()
    for path in _optimization_sources():
        source = path.read_text(encoding="utf-8")
        lowered = source.lower()
        for token in FORBIDDEN_IMPORTS:
            assert token.lower() not in lowered, f"{path.name} references {token}"


def test_optimization_sources_contain_no_raw_sql():
    for path in _optimization_sources():
        source = path.read_text(encoding="utf-8")
        match = RAW_SQL.search(source)
        assert match is None, f"{path.name} contains raw SQL: {match}"


def test_run_optimization_accepts_payloads_not_sessions():
    parameters = inspect.signature(run_optimization).parameters
    assert "session" not in parameters
    assert "engine" not in parameters
    for payload in ("replay_run", "entities", "supplier_links"):
        assert payload in parameters
    assert "config" in parameters
    assert "solver" in parameters


def test_run_optimization_module_level_imports_are_data_only():
    from backend.app.analytics.optimization import optimization as module

    imported = set(getattr(module, "__dict__", {}))
    for name in ("session", "engine", "Session", "create_engine"):
        assert name not in imported


def test_run_optimization_never_touches_the_database(monkeypatch, tmp_path):
    import backend.app.core.database as database

    def _explode(*args, **kwargs):
        raise AssertionError("optimization must not touch the database")

    monkeypatch.setattr(database, "AsyncSessionLocal", _explode)
    from backend.app.tests.optimization_support import (
        build_case,
        short_outage_scenario,
    )

    case = build_case(short_outage_scenario())
    run = run_optimization(
        case["run"], case["entities"], case["inputs"]["supplier_links"],
        forecast_by_series=case["inputs"]["forecasts"],
    )
    assert run["result"]["status"] in ("OPTIMAL", "FEASIBLE", "INFEASIBLE",
                                       "UNBOUNDED", "ERROR", "NO_DATA")
