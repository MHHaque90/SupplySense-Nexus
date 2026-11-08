"""Phase 8 traceability tests (every field preserved)."""

from backend.app.analytics.simulation import traceability
from backend.app.analytics.simulation.types import SimulationScenario


def _scenario():
    from backend.app.analytics.simulation.types import DisruptionEvent

    return SimulationScenario(
        scenario_id="S1", analysis_date="2026-06-30", horizon_days=14,
        event=DisruptionEvent(event_id="E1", event_type="SUPPLIER_DISRUPTION",
                              duration_days=14, supply_reduction=1.0,
                              affected_suppliers=["S1"]),
        probability_mode="explicit", probability=0.2,
        probability_source="USER_ASSUMED", simulation_count=50,
        random_seed=7, selection_basis="risk_record:R1",
    )


def test_trace_chain_complete():
    trace = traceability.build_trace(
        _scenario(), "P1", "W1", ["S1", "S2"],
        {"model_name": "holt", "origin": "2026-06-30", "horizon": 14},
        120.0, ["PO1", "PO2"],
    )
    assert trace["scenario_id"] == "S1"
    assert trace["event_id"] == "E1"
    assert trace["event_type"] == "SUPPLIER_DISRUPTION"
    assert trace["product_id"] == "P1"
    assert trace["warehouse_id"] == "W1"
    assert trace["supplier_ids"] == ["S1", "S2"]
    assert trace["baseline_on_hand"] == 120.0
    assert trace["forecast_model"] == "holt"
    assert trace["forecast_origin"] == "2026-06-30"
    assert trace["forecast_horizon"] == 14
    assert trace["inbound_sources"] == ["PO1", "PO2"]
    assert trace["probability_mode"] == "explicit"
    assert trace["probability_source"] == "USER_ASSUMED"
    assert trace["random_seed"] == 7
    assert trace["simulation_count"] == 50
    assert trace["selection_basis"] == "risk_record:R1"
    assert trace["data_source_label"] == "simulated"


def test_trace_without_event():
    scenario = _scenario()
    scenario.event = None
    trace = traceability.build_trace(
        scenario, "P1", "W1", [], {}, 0.0, [],
    )
    assert trace["event_id"] is None
    assert trace["supplier_ids"] == []
