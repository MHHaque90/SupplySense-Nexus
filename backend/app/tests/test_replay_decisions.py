"""Phase 9 decision contract tests."""

import pytest

from backend.app.analytics.replay import decisions
from backend.app.analytics.replay.types import DECISION_TYPES, Decision


def test_decision_contract_fields():
    decision = decisions.build_decision(
        "R1", "EXPEDITE_INBOUND", description="Move inbound earlier.",
        affected_suppliers=["S1"], affected_products=["P1"],
        quantities={"expedite_units": 100.0},
        timing={"start_day": 0, "delay_reduction_days": 5},
        cost_assumptions={"expedite_cost": 5000.0},
        assumptions=["Arrives 5 days earlier."],
    )
    assert decision.decision_type == "EXPEDITE_INBOUND"
    assert decision.quantities == {"expedite_units": 100.0}
    assert decision.timing == {"start_day": 0, "delay_reduction_days": 5}
    assert decision.cost_assumptions == {"expedite_cost": 5000.0}
    assert decision.source == "user_defined"
    assert any("decision assumption" in note for note in decision.assumptions)
    payload = decision.to_dict()
    assert payload["decision_id"] == decision.decision_id


def test_deterministic_ids():
    first = decisions.build_decision("R1", "NO_ACTION")
    second = decisions.build_decision("R1", "NO_ACTION")
    assert first.decision_id == second.decision_id
    other = decisions.build_decision("R2", "NO_ACTION")
    assert other.decision_id != first.decision_id
    assert "no_action" in first.decision_id


def test_all_eight_decision_types():
    assert set(DECISION_TYPES) == {
        "NO_ACTION", "EXPEDITE_INBOUND", "ALTERNATIVE_SUPPLIER",
        "SUPPLIER_ALLOCATION_CHANGE", "INVENTORY_TRANSFER",
        "DEMAND_ADJUSTMENT", "PURCHASE_ORDER_ADJUSTMENT", "COMBINED_ACTION",
    }
    for decision_type in DECISION_TYPES:
        components = None
        if decision_type == "COMBINED_ACTION":
            components = [decisions.build_decision("R1", "NO_ACTION")]
        decision = decisions.build_decision("R1", decision_type, components=components)
        assert decision.decision_type == decision_type
    with pytest.raises(ValueError):
        decisions.build_decision("R1", "TELEPORT_INVENTORY")


def test_no_action_control_arm():
    decision = decisions.build_no_action("R1")
    assert decision.decision_type == "NO_ACTION"
    assert decision.quantities == {} and decision.timing == {}


def test_combined_action_rules():
    with pytest.raises(ValueError):
        decisions.build_decision("R1", "COMBINED_ACTION")
    nested = decisions.build_decision(
        "R1", "COMBINED_ACTION",
        components=[decisions.build_decision("R1", "NO_ACTION")],
    )
    with pytest.raises(ValueError):
        decisions.build_decision("R1", "COMBINED_ACTION", components=[nested])


def test_decision_from_dict():
    payload = {
        "decision_type": "EXPEDITE_INBOUND",
        "description": "Expedite selected inbound",
        "affected_suppliers": ["SUP-001"],
        "affected_products": ["PROD-001"],
        "affected_warehouses": ["WH-NORTH"],
        "quantities": {"expedite_units": 100},
        "timing": {"start_day": 0, "end_day": 7, "delay_reduction_days": 5},
        "cost_assumptions": {"expedite_cost": 5000},
        "assumptions": ["Expedited inbound arrives 5 days earlier."],
        "source": "user_defined",
    }
    decision = decisions.decision_from_dict("R9", payload)
    assert isinstance(decision, Decision)
    assert decision.quantities == {"expedite_units": 100.0}
    assert decision.timing["delay_reduction_days"] == 5
    with pytest.raises(ValueError):
        decisions.decision_from_dict("R9", ["not", "a", "dict"])
    with pytest.raises(ValueError):
        decisions.decision_from_dict("R9", {"decision_type": "NOPE"})
