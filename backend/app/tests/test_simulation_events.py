"""Phase 8 disruption event tests (all seven types + templates)."""

import pytest

from backend.app.analytics.simulation import events
from backend.app.analytics.simulation.types import DisruptionEvent


def _event(event_type, **overrides):
    params = {
        "event_id": "E1", "event_type": event_type, "name": event_type,
        "duration_days": 14,
        "affected_suppliers": ["S1"],
        "affected_warehouses": ["W1"],
        "supply_reduction": 0.5,
        "lead_time_delay_days": 5,
        "demand_multiplier": 1.2,
        "warehouse_available": False,
    }
    params.update(overrides)
    return DisruptionEvent(**params)


def test_supplier_disruption_contract():
    event = _event("SUPPLIER_DISRUPTION")
    notes = events.validate_event(event)
    assert any("supply_reduction = 0.5" in note for note in notes)
    assert any("not an observed historical fact" in note for note in notes)
    with pytest.raises(ValueError):
        events.validate_event(_event("SUPPLIER_DISRUPTION", affected_suppliers=[]))
    with pytest.raises(ValueError):
        events.validate_event(_event("SUPPLIER_DISRUPTION", supply_reduction=0.0))


def test_shipment_and_lead_time_delays():
    events.validate_event(_event("SHIPMENT_DELAY"))
    events.validate_event(_event("LEAD_TIME_DELAY"))
    with pytest.raises(ValueError):
        events.validate_event(_event("SHIPMENT_DELAY", lead_time_delay_days=0))


def test_supply_reduction_bounds():
    events.validate_event(_event("SUPPLY_REDUCTION"))
    with pytest.raises(ValueError):
        events.validate_event(_event("SUPPLY_REDUCTION", supply_reduction=1.5))
    with pytest.raises(ValueError):
        events.validate_event(_event("SUPPLY_REDUCTION", supply_reduction=0.0))


def test_warehouse_disruption_contract():
    events.validate_event(_event("WAREHOUSE_DISRUPTION"))
    with pytest.raises(ValueError):
        events.validate_event(_event("WAREHOUSE_DISRUPTION", affected_warehouses=[]))
    with pytest.raises(ValueError):
        events.validate_event(_event("WAREHOUSE_DISRUPTION", warehouse_available=True))


def test_demand_shock_contract():
    events.validate_event(_event("DEMAND_SHOCK"))
    with pytest.raises(ValueError):
        events.validate_event(_event("DEMAND_SHOCK", demand_multiplier=1.0))
    with pytest.raises(ValueError):
        events.validate_event(_event("DEMAND_SHOCK", demand_multiplier=0.0))


def test_combined_components_validated():
    component = _event("SHIPMENT_DELAY")
    event = _event("COMBINED_DISRUPTION", components=[component])
    notes = events.validate_event(event)
    assert any("Combined components" in note for note in notes)
    nested = _event("COMBINED_DISRUPTION", components=[_event("COMBINED_DISRUPTION")])
    with pytest.raises(ValueError):
        events.validate_event(nested)


def test_unknown_type_and_bad_duration_rejected():
    with pytest.raises(ValueError):
        events.validate_event(_event("VOLCANO"))
    with pytest.raises(ValueError):
        events.validate_event(_event("SUPPLY_REDUCTION", duration_days=0))


def test_templates_expose_assumptions():
    for template in ("SUPPLIER_OUTAGE", "SUPPLIER_DELAY", "SHIPMENT_DELAY",
                     "SUPPLY_REDUCTION", "WAREHOUSE_DISRUPTION", "DEMAND_SPIKE",
                     "COMBINED_DISRUPTION"):
        event = events.apply_template(template, "T1")
        assert event.assumptions, template
        assert event.data_source_label == "simulated"
    with pytest.raises(ValueError):
        events.apply_template("NOPE", "T1")


def test_event_describes_condition_not_prediction():
    text = events.describe_event(_event("SUPPLIER_DISRUPTION", name="Outage"))
    assert "conditional on the event occurring" in text
    assert "will occur" not in text
