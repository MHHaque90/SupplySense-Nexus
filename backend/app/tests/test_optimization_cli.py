"""Phase 10 CLI integration tests (spec section 25.J).

The ``optimization`` subcommand is exercised through ``main()`` with
dataset loaders monkeypatched to SYNTHETIC frames; no real dataset
contents are required beyond an available database connection.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

import scripts.analyze_supply_chain as cli
from backend.app.analytics.datasets import demand as demand_ds
from backend.app.analytics.datasets import inventory as inventory_ds
from backend.app.analytics.datasets import procurement as procurement_ds
from backend.app.analytics.datasets import suppliers as suppliers_ds
from backend.app.analytics.inventory import forecast_inputs
from backend.app.tests.replay_support import (
    make_forecasts,
    make_po_lines,
    make_shipments,
    make_snapshots,
    make_supplier_links,
)


@pytest.fixture
def synthetic_loaders(monkeypatch):
    """Point every dataset loader at in-memory SYNTHETIC frames."""
    empty = pd.DataFrame()
    monkeypatch.setattr(cli, "_check_connection", _always_connected)
    monkeypatch.setattr(inventory_ds, "load_snapshots", _stub(make_snapshots()))
    monkeypatch.setattr(procurement_ds, "load_purchase_orders", _stub(make_po_lines()))
    monkeypatch.setattr(procurement_ds, "load_shipments", _stub(make_shipments()))
    monkeypatch.setattr(suppliers_ds, "load_suppliers", _stub(make_supplier_links()))
    monkeypatch.setattr(demand_ds, "load_demand", _stub(empty))
    monkeypatch.setattr(forecast_inputs, "load_persisted_forecasts", _stub(empty))
    monkeypatch.setattr(
        forecast_inputs, "frame_to_inputs", lambda frame: make_forecasts(),
    )


async def _always_connected() -> bool:
    return True


async def _always_disconnected() -> bool:
    return False


def _stub(frame):
    async def _load(*args, **kwargs):
        return frame.copy()

    return _load


def _base_args(*extra: str) -> list[str]:
    return [
        "optimization",
        "--scenario", "SUPPLIER_OUTAGE",
        "--supplier-id", "S1",
        "--duration-days", "3",
        *extra,
    ]


def test_end_to_end_run_writes_json_and_markdown(synthetic_loaders, tmp_path,
                                                 capsys):
    json_path = tmp_path / "plan.json"
    markdown_path = tmp_path / "plan.md"
    exit_code = cli.main(_base_args(
        "--objective", "minimize_total_cost",
        "--output-json", str(json_path),
        "--output-markdown", str(markdown_path),
    ))
    assert exit_code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["report_type"] == "optimization"
    assert len(payload["sections"]) == 21
    assert payload["feasibility_status"]["status"] in (
        "OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNBOUNDED", "ERROR", "NO_DATA",
    )
    assert payload["synthetic"] is True
    assert payload["data_source_label"] == "simulated"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert markdown.startswith("# Optimization Run Report (Synthetic / Simulated Data)")
    captured = capsys.readouterr()
    assert "Status:" in captured.out


def test_emits_json_to_stdout_without_output_files(synthetic_loaders, capsys):
    exit_code = cli.main(_base_args())
    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"report_type": "optimization"' in captured.out
    assert "Status:" in captured.out


def test_missing_scenario_returns_exit_2(synthetic_loaders, capsys):
    exit_code = cli.main(["optimization", "--supplier-id", "S1"])
    assert exit_code == 2
    assert "Provide --scenario-json or --scenario" in capsys.readouterr().out


def test_unknown_template_returns_exit_2(synthetic_loaders, capsys):
    exit_code = cli.main(_base_args()[:1] + ["--scenario", "NOT_A_TEMPLATE"])
    assert exit_code == 2
    assert "Invalid scenario definition" in capsys.readouterr().out


def test_tradeoff_without_penalty_returns_exit_2(synthetic_loaders, capsys):
    exit_code = cli.main(_base_args(
        "--objective", "cost_shortage_tradeoff",
    ))
    assert exit_code == 2
    assert "--shortage-penalty > 0" in capsys.readouterr().out


def test_nonpositive_budget_returns_exit_2(synthetic_loaders, capsys):
    exit_code = cli.main(_base_args("--budget", "-5"))
    assert exit_code == 2
    assert "Invalid --budget" in capsys.readouterr().out


def test_out_of_range_fulfillment_returns_exit_2(synthetic_loaders, capsys):
    exit_code = cli.main(_base_args("--min-fulfillment", "1.5"))
    assert exit_code == 2
    assert "Invalid --min-fulfillment" in capsys.readouterr().out


def test_out_of_range_horizon_returns_exit_2(synthetic_loaders, capsys):
    exit_code = cli.main(_base_args("--horizon-days", "0"))
    assert exit_code == 2
    assert "Invalid --horizon-days" in capsys.readouterr().out


def test_reversed_date_range_returns_exit_2(synthetic_loaders, capsys):
    exit_code = cli.main(_base_args(
        "--start-date", "2026-07-01", "--end-date", "2026-06-01",
    ))
    assert exit_code == 2
    assert "Invalid dates" in capsys.readouterr().out


def test_malformed_scenario_json_returns_exit_2(synthetic_loaders, capsys,
                                                tmp_path):
    bad_path = tmp_path / "bad-scenario.json"
    bad_path.write_text("{not json", encoding="utf-8")
    exit_code = cli.main(_base_args("--scenario-json", str(bad_path)))
    assert exit_code == 2
    assert "Invalid --scenario-json" in capsys.readouterr().out


def test_empty_dataset_returns_exit_1(synthetic_loaders, monkeypatch, capsys):
    empty = pd.DataFrame()
    monkeypatch.setattr(inventory_ds, "load_snapshots", _stub(empty))
    monkeypatch.setattr(procurement_ds, "load_purchase_orders", _stub(empty))
    exit_code = cli.main(_base_args())
    assert exit_code == 1
    assert "Dataset is empty" in capsys.readouterr().out


def test_unavailable_database_returns_exit_2(monkeypatch, capsys):
    async def _offline() -> bool:
        return False

    monkeypatch.setattr(cli, "_check_connection", _offline)
    exit_code = cli.main(_base_args())
    assert exit_code == 2
    out = capsys.readouterr().out
    assert "database is unavailable" in out


def test_invalid_time_limit_returns_exit_2(synthetic_loaders, capsys):
    exit_code = cli.main(_base_args("--time-limit", "0"))
    assert exit_code == 2
    assert "Invalid --time-limit" in capsys.readouterr().out


def test_shortage_objective_runs_end_to_end(synthetic_loaders, tmp_path):
    json_path = tmp_path / "shortage.json"
    exit_code = cli.main(_base_args(
        "--objective", "minimize_shortage",
        "--output-json", str(json_path),
    ))
    assert exit_code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["objective"]["name"] == "minimize_shortage"
    assert payload["feasibility_status"]["status"] in ("OPTIMAL", "FEASIBLE")


def test_written_report_keeps_banned_wording_out(synthetic_loaders, tmp_path):
    import re

    markdown_path = tmp_path / "plan.md"
    exit_code = cli.main(_base_args("--output-markdown", str(markdown_path)))
    assert exit_code == 0
    markdown = markdown_path.read_text(encoding="utf-8")
    banned = re.compile(r"\b(best|should|recommend|ideal|perfect)\b", re.IGNORECASE)
    assert banned.search(markdown) is None


def test_output_json_path_must_exist_directory(synthetic_loaders, tmp_path):
    missing = tmp_path / "missing-dir" / "plan.json"
    with pytest.raises(OSError):
        cli.main(_base_args("--output-json", str(missing)))
