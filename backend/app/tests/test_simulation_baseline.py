"""Phase 8 baseline generation tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.simulation import baseline
from backend.app.analytics.simulation.types import DEFAULT_SIMULATION_CONFIG


def _frames():
    shipments = pd.DataFrame({
        "shipment_id": ["SH1"],
        "po_id": ["PO1"],
        "supplier_id": ["S1"],
        "expected_arrival_date": [date(2026, 7, 3)],
        "actual_arrival_date": [pd.NaT],
    })
    po_lines = pd.DataFrame({
        "po_id": ["PO1"],
        "supplier_id": ["S1"],
        "product_id": ["P1"],
        "order_date": [date(2026, 6, 20)],
        "quantity": [40.0],
    })
    return shipments, po_lines


def test_baseline_generation_and_start_state():

    shipments, po_lines = _frames()
    state = baseline.build_baseline_series(
        "P1", "W1", 100.0, [10.0] * 14, [8.0] * 14, [12.0] * 14,
        date(2026, 6, 30), 14, shipments, po_lines, date(2026, 6, 30),
        {"model_name": "naive"},
    )
    assert state["on_hand"] == 100.0
    assert state["demand_point"] == [10.0] * 14
    assert len(state["forecast_dates"]) == 14
    assert state["forecast_dates"][0] == "2026-07-01"
    assert state["forecast_meta"]["model_name"] == "naive"


def test_baseline_reproducibility():

    shipments, po_lines = _frames()
    kwargs = {
        "product_id": "P1", "warehouse_id": "W1", "on_hand": 100.0,
        "forecast_point": [10.0] * 14, "forecast_lower": [8.0] * 14,
        "forecast_upper": [12.0] * 14, "origin": date(2026, 6, 30),
        "horizon_days": 14, "shipments": shipments, "po_lines": po_lines,
        "analysis_date": date(2026, 6, 30),
    }
    first = baseline.build_baseline_series(**kwargs)
    second = baseline.build_baseline_series(**kwargs)
    assert first == second


def test_baseline_unaffected_by_disruption_assumptions():

    shipments, po_lines = _frames()
    state = baseline.build_baseline_series(
        "P1", "W1", 100.0, [10.0] * 7, [8.0] * 7, [12.0] * 7,
        date(2026, 6, 30), 7, shipments, po_lines, date(2026, 6, 30),
    )
    # Baseline carries no disruption parameters at all.
    assert "supply_reduction" not in state
    assert "event" not in state
    assert state["inbound"] == {"2026-07-03": 40.0}


def test_short_forecast_extended_transparently():
    from backend.app.analytics.inventory.types import ForecastInput
    from backend.app.analytics.simulation import runner as runner_mod
    from backend.app.analytics.simulation.types import DisruptionEvent, SimulationScenario

    event = DisruptionEvent(
        event_id="E", event_type="SUPPLY_REDUCTION",
        duration_days=7, supply_reduction=0.5,
    )
    scenario = SimulationScenario(
        scenario_id="S", analysis_date="2026-06-30", horizon_days=14, event=event,
        affected_entities=[{"entity_type": "product", "product_id": "P1",
                            "warehouse_id": "W1"}],
    )
    shipments, po_lines = _frames()
    short = ForecastInput(
        product_id="P1", warehouse_id="W1", origin="2026-06-30",
        forecast_dates=[f"2026-07-{day:02d}" for day in range(1, 8)],
        horizon=7, point=[10.0] * 7, lower=[8.0] * 7, upper=[12.0] * 7,
    )
    snapshots = pd.DataFrame({
        "product_id": ["P1"], "warehouse_id": ["W1"],
        "snapshot_date": [date(2026, 6, 30)], "on_hand": [200.0],
    })
    result = runner_mod.run_scenario(
        scenario, {"P1|W1": short}, snapshots, shipments, po_lines,
        pd.DataFrame(), date(2026, 6, 30), DEFAULT_SIMULATION_CONFIG,
    )
    assert len(result["per_entity"]) == 1
    assert len(result["traces"]) == 1
    assert any("extended by repeating" in note for note in result["traces"][0].get("notes", []))
