"""Phase 9 no-database-access tests.

The Decision Replay Lab operates entirely on in-memory frames passed
by its caller. No replay module may import the database stack, open a
session, or embed raw SQL.
"""

import inspect
import re
from pathlib import Path

import backend.app.analytics.replay as replay_package
from backend.app.analytics.replay import replay as replay_mod

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


def _replay_sources():
    root = Path(replay_package.__file__).parent
    return sorted(root.glob("*.py"))


def test_replay_sources_never_reference_the_database_stack():
    assert _replay_sources()
    for path in _replay_sources():
        source = path.read_text(encoding="utf-8")
        lowered = source.lower()
        for token in FORBIDDEN_IMPORTS:
            assert token.lower() not in lowered, f"{path.name} references {token}"


def test_replay_sources_contain_no_raw_sql():
    for path in _replay_sources():
        source = path.read_text(encoding="utf-8")
        match = RAW_SQL.search(source)
        assert match is None, f"{path.name} contains raw SQL: {match}"


def test_run_replay_accepts_frames_not_sessions():
    parameters = inspect.signature(replay_mod.run_replay).parameters
    assert "session" not in parameters
    assert "engine" not in parameters
    for frame in (
        "snapshots", "shipments", "po_lines", "supplier_links",
        "forecast_by_series",
    ):
        assert frame in parameters


def test_run_replay_module_level_imports_are_data_only():
    module = inspect.getmodule(replay_mod)
    imported = set(getattr(module, "__dict__", {}))
    for name in ("session", "engine", "Session", "create_engine"):
        assert name not in imported
