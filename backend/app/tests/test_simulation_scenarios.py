"""Phase 8 scenario contract and targeting tests."""

import pytest

from backend.app.analytics.simulation import events, scenarios, targets
from backend.app.analytics.simulation.types import DisruptionEvent


def _event(**overrides):
    params = {
        "event_id": "E1", "event_type": "SUPPLY_REDUCTION", "name": "Cut",
        "duration_days": 14, "supply_reduction": 0.4,
    }
    params.update(overrides)
    return DisruptionEvent(**params)


def test_valid_scenario_contract():
    scenario = scenarios.build_scenario(
        scenario_id="S1", event=_event(), analysis_date="2026-06-30",
        horizon_days=28, simulation_count=10, random_seed=7,
    )
    assert scenario.horizon_days == 28
    assert scenario.simulation_count == 10
    assert scenario.random_seed == 7
    assert scenario.probability_source == "DETERMINISTIC"
    assert scenario.data_source_label == "simulated"
    assert scenario.selection_basis == "explicit_user_selection"
    assert any("horizon_days = 28" in item for item in scenario.assumptions)


def test_invalid_horizon_rejected():
    with pytest.raises(ValueError):
        scenarios.build_scenario(
            scenario_id="S1", event=_event(), analysis_date="2026-06-30",
            horizon_days=0,
        )
    with pytest.raises(ValueError):
        scenarios.build_scenario(
            scenario_id="S1", event=_event(), analysis_date="2026-06-30",
            horizon_days=500,
        )
    with pytest.raises(ValueError):
        scenarios.build_scenario(
            scenario_id="S1", event=_event(), analysis_date="2026-06-30",
            simulation_count=0,
        )


def test_invalid_event_parameters_rejected():
    with pytest.raises(ValueError):
        scenarios.build_scenario(
            scenario_id="S1",
            event=DisruptionEvent(event_id="E", event_type="SUPPLY_REDUCTION",
                                  duration_days=14, supply_reduction=0.0),
            analysis_date="2026-06-30",
        )


def test_explicit_targeting():
    entities = targets.resolve_explicit(
        supplier_ids=["S1"], product_ids=["P1"], warehouse_ids=["W1"]
    )
    assert {"entity_type": "supplier", "supplier_id": "S1"} in entities
    assert {"entity_type": "product", "product_id": "P1"} in entities
    assert {"entity_type": "warehouse", "warehouse_id": "W1"} in entities
    assert targets.resolve_explicit() == []


def test_supplier_product_expansion():
    import pandas as pd

    links = pd.DataFrame({
        "supplier_id": ["S1", "S1", "S2"],
        "product_id": ["P1", "P2", "P1"],
    })
    entities = targets.resolve_supplier_products("S1", links)
    assert {"entity_type": "supplier", "supplier_id": "S1"} in entities
    assert {"entity_type": "supplier_product", "supplier_id": "S1",
            "product_id": "P1"} in entities
    assert len([e for e in entities if e["entity_type"] == "supplier_product"]) == 2


def test_risk_record_targeting_keeps_basis():
    record = {"risk_id": "supplier:supplier:S1:2026-06-30", "supplier_id": "S1"}
    entities, basis = targets.resolve_risk_record(record)
    assert basis == "risk_record:supplier:supplier:S1:2026-06-30"
    assert {"entity_type": "supplier", "supplier_id": "S1"} in entities
    record = {"risk_id": "inventory:product_warehouse:P1|W1:2026-06-30",
              "product_id": "P1", "warehouse_id": "W1"}
    entities, _ = targets.resolve_risk_record(record)
    assert {"entity_type": "product", "product_id": "P1",
            "warehouse_id": "W1"} in entities


def test_event_templates_cover_types():
    for template, event_type in (
        ("SUPPLIER_OUTAGE", "SUPPLIER_DISRUPTION"),
        ("SUPPLIER_DELAY", "LEAD_TIME_DELAY"),
        ("SHIPMENT_DELAY", "SHIPMENT_DELAY"),
        ("SUPPLY_REDUCTION", "SUPPLY_REDUCTION"),
        ("WAREHOUSE_DISRUPTION", "WAREHOUSE_DISRUPTION"),
        ("DEMAND_SPIKE", "DEMAND_SHOCK"),
        ("COMBINED_DISRUPTION", "COMBINED_DISRUPTION"),
    ):
        event = events.apply_template(template, "T")
        assert event.event_type == event_type
