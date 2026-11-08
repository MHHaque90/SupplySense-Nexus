"""Phase 9 targeting tests: explicit targets, membership, relationships."""

import pytest

from backend.app.analytics.replay import decisions, validation
from backend.app.analytics.simulation import runner as runner_mod
from backend.app.tests.replay_support import HORIZON_DAYS, make_inputs

SUPPLIERS = {"S1", "S2"}
PRODUCTS = {"P1", "P2"}
WAREHOUSES = {"W1", "W2"}
LINKS = {("S1", "P1"), ("S2", "P2")}
SERIES = {("P1", "W1"), ("P1", "W2"), ("P2", "W1"), ("P2", "W2")}
ON_HAND = {key: 40.0 for key in SERIES}


def _validate(decision, horizon=HORIZON_DAYS):
    return validation.validate_decision(
        decision, horizon, SUPPLIERS, PRODUCTS, WAREHOUSES, LINKS, SERIES, ON_HAND,
    )


def test_supplier_target_resolves_to_series():
    inputs = make_inputs()
    scenario_targets = [{"entity_type": "supplier", "supplier_id": "S1"}]
    keys = runner_mod.resolve_series(
        scenario_targets, inputs["snapshots"], inputs["supplier_links"]
    )
    assert keys == [("P1", "W1"), ("P1", "W2")]


def test_unknown_supplier_rejected():
    decision = decisions.build_decision(
        "R1", "EXPEDITE_INBOUND", affected_suppliers=["S9"],
        affected_products=["P1"],
        quantities={"expedite_units": 5.0},
        timing={"start_day": 0, "end_day": 7, "delay_reduction_days": 2},
    )
    with pytest.raises(ValueError, match="Unknown supplier"):
        _validate(decision)


def test_unknown_product_rejected():
    decision = decisions.build_decision(
        "R1", "EXPEDITE_INBOUND", affected_suppliers=["S1"],
        affected_products=["P9"],
        quantities={"expedite_units": 5.0},
        timing={"start_day": 0, "end_day": 7, "delay_reduction_days": 2},
    )
    with pytest.raises(ValueError, match="Unknown product"):
        _validate(decision)


def test_unknown_warehouse_rejected():
    decision = decisions.build_decision(
        "R1", "EXPEDITE_INBOUND", affected_suppliers=["S1"],
        affected_products=["P1"], affected_warehouses=["W9"],
        quantities={"expedite_units": 5.0},
        timing={"start_day": 0, "end_day": 7, "delay_reduction_days": 2},
    )
    with pytest.raises(ValueError, match="Unknown warehouse"):
        _validate(decision)


def test_alternative_supplier_requires_explicit_selection():
    decision = decisions.build_decision(
        "R1", "ALTERNATIVE_SUPPLIER",
        affected_products=["P1"], quantities={"switch_units": 5.0},
    )
    with pytest.raises(ValueError, match="explicit affected_suppliers"):
        _validate(decision)
    supplier_choice = decisions.build_decision(
        "R1", "ALTERNATIVE_SUPPLIER",
        affected_suppliers=["S1"], affected_products=["P1"],
        quantities={"switch_units": 5.0},
    )
    notes = _validate(supplier_choice)
    assert any("explicit user selection" in note for note in notes)
    assert any("not selected or ranked" in note for note in notes)


def test_alternative_supplier_must_supply_product():
    decision = decisions.build_decision(
        "R1", "ALTERNATIVE_SUPPLIER",
        affected_suppliers=["S2"], affected_products=["P1"],
        quantities={"switch_units": 5.0},
    )
    with pytest.raises(ValueError, match="does not supply"):
        _validate(decision)


def test_membership_accepts_in_scope_pair():
    decision = decisions.build_decision(
        "R1", "EXPEDITE_INBOUND",
        affected_products=["P1"], affected_warehouses=["W1"],
        quantities={"expedite_units": 5.0},
        timing={"start_day": 0, "end_day": 7, "delay_reduction_days": 2},
    )
    validation.validate_scenario_membership(decision, SERIES)


def test_membership_rejects_out_of_scope_warehouse():
    decision = decisions.build_decision(
        "R1", "EXPEDITE_INBOUND",
        affected_products=["P1"], affected_warehouses=["W9"],
        quantities={"expedite_units": 5.0},
        timing={"start_day": 0, "end_day": 7, "delay_reduction_days": 2},
    )
    with pytest.raises(ValueError, match="outside scenario scope"):
        validation.validate_scenario_membership(decision, SERIES)


def test_membership_rejects_product_without_scenario_series():
    decision = decisions.build_decision(
        "R1", "DEMAND_ADJUSTMENT",
        affected_products=["P9"], quantities={"demand_multiplier": 1.1},
        timing={"start_day": 0, "end_day": 7},
    )
    with pytest.raises(ValueError, match="outside scenario scope"):
        validation.validate_scenario_membership(decision, SERIES)


def test_transfer_membership_requires_both_warehouses():
    decision = decisions.build_decision(
        "R1", "INVENTORY_TRANSFER",
        affected_products=["P1"], affected_warehouses=["W1", "W9"],
        quantities={"transfer_units": 5.0},
    )
    with pytest.raises(ValueError, match="outside scenario scope"):
        validation.validate_scenario_membership(decision, SERIES)


def test_allocation_targets_must_be_known_suppliers():
    decision = decisions.build_decision(
        "R1", "SUPPLIER_ALLOCATION_CHANGE",
        affected_suppliers=["S1", "S2"], affected_products=["P1"],
        quantities={"S1": 60.0, "S9": 40.0},
    )
    with pytest.raises(ValueError, match="Unknown supplier"):
        _validate(decision)
