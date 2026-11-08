"""Phase 9 decision validation tests (every rejection case)."""

import pytest

from backend.app.analytics.replay import decisions, validation

IDS = {
    "supplier_ids": {"S1", "S2"},
    "product_ids": {"P1", "P2"},
    "warehouse_ids": {"W1", "W2"},
    "supplier_products": {("S1", "P1"), ("S2", "P2")},
    "series_keys": {("P1", "W1"), ("P2", "W1")},
    "on_hand": {("P1", "W1"): 100.0, ("P2", "W1"): 50.0},
}


def _validate(decision, horizon=28):
    return validation.validate_decision(
        decision, horizon,
        IDS["supplier_ids"], IDS["product_ids"], IDS["warehouse_ids"],
        IDS["supplier_products"], IDS["series_keys"], IDS["on_hand"],
    )


def _decision(decision_type, **overrides):
    params = {
        "affected_suppliers": ["S1"], "affected_products": ["P1"],
        "affected_warehouses": ["W1"],
        "quantities": {"expedite_units": 10.0},
        "timing": {"start_day": 0, "end_day": 7, "delay_reduction_days": 5},
    }
    params.update(overrides)
    return decisions.build_decision("R1", decision_type, **params)


def test_valid_decision_passes():
    notes = _validate(_decision("EXPEDITE_INBOUND"))
    assert any("PASS" in note for note in notes)


@pytest.mark.parametrize("field,value", [
    ("affected_suppliers", ["SX"]),
    ("affected_products", ["PX"]),
    ("affected_warehouses", ["WX"]),
])
def test_unknown_ids_rejected(field, value):
    with pytest.raises(ValueError, match="Unknown"):
        _validate(_decision("EXPEDITE_INBOUND", **{field: value}))


def test_quantity_must_be_positive():
    with pytest.raises(ValueError, match="must be > 0"):
        _validate(_decision("EXPEDITE_INBOUND", quantities={"expedite_units": 0.0}))
    with pytest.raises(ValueError, match="must be > 0"):
        _validate(_decision("EXPEDITE_INBOUND", quantities={"expedite_units": -5.0}))


def test_invalid_timing_rejected():
    with pytest.raises(ValueError, match="outside"):
        _validate(_decision("EXPEDITE_INBOUND", timing={"start_day": 30, "end_day": 31}))
    with pytest.raises(ValueError, match="end_day"):
        _validate(_decision("EXPEDITE_INBOUND", timing={"start_day": 5, "end_day": 5}))
    with pytest.raises(ValueError, match="end_day"):
        _validate(_decision("EXPEDITE_INBOUND", timing={"start_day": 0, "end_day": 99}))


def test_supplier_product_link_required():
    with pytest.raises(ValueError, match="does not supply"):
        _validate(_decision("ALTERNATIVE_SUPPLIER",
                            affected_suppliers=["S2"], affected_products=["P1"]))


def test_insufficient_source_inventory_rejected():
    with pytest.raises(ValueError, match="Insufficient source inventory"):
        _validate(decisions.build_decision(
            "R1", "INVENTORY_TRANSFER",
            affected_products=["P2"], affected_warehouses=["W1", "W2"],
            quantities={"transfer_units": 500.0},
            timing={"start_day": 0, "end_day": 7},
        ))


def test_transfer_warehouse_rules():
    with pytest.raises(ValueError, match="exactly two warehouses"):
        _validate(decisions.build_decision(
            "R1", "INVENTORY_TRANSFER",
            affected_products=["P1"], affected_warehouses=["W1"],
            quantities={"transfer_units": 5.0},
        ))


def test_scenario_membership_rejected():
    decision = _decision("EXPEDITE_INBOUND", affected_products=["P2"],
                         affected_warehouses=["W2"])
    with pytest.raises(ValueError, match="outside scenario scope"):
        validation.validate_scenario_membership(decision, {("P1", "W1")})


def test_combined_components_validated_in_order():
    decision = decisions.build_decision(
        "R1", "COMBINED_ACTION",
        components=[
            decisions.build_decision("R1", "NO_ACTION"),
            _decision("EXPEDITE_INBOUND"),
        ],
    )
    notes = _validate(decision)
    assert any("declared order" in note for note in notes)


def test_unknown_decision_type_rejected_at_construction():
    with pytest.raises(ValueError, match="Unknown decision type"):
        decisions.build_decision("R1", "TIME_TRAVEL")
