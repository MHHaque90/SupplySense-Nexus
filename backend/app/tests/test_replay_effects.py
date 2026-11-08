"""Phase 9 decision effect tests (one group per type + copy-on-write)."""

import pytest

from backend.app.analytics.replay import decisions, effects

HORIZON = 10


def _schedule():
    return [
        {"date": "2026-07-03", "day_offset": 2, "quantity": 100.0,
         "supplier_id": "S1", "po_id": "PO1",
         "affected_by_event": False, "event_id": None},
        {"date": "2026-07-08", "day_offset": 7, "quantity": 50.0,
         "supplier_id": "S1", "po_id": "PO2",
         "affected_by_event": False, "event_id": None},
    ]


def _decision(decision_type, **overrides):
    params = {
        "affected_suppliers": ["S1"], "affected_products": ["P1"],
        "affected_warehouses": ["W1"],
    }
    params.update(overrides)
    return decisions.build_decision("R1", decision_type, **params)


def test_no_action_identity():
    demand = [10.0] * HORIZON
    schedule = _schedule()
    result = effects.apply_decision(demand, schedule, 80.0, _decision("NO_ACTION"), HORIZON)
    assert result["demand"] == demand
    assert result["schedule"] == schedule
    assert result["on_hand"] == 80.0


def test_expedite_inbound_moves_arrivals_earlier():
    decision = _decision(
        "EXPEDITE_INBOUND",
        quantities={"expedite_units": 60.0},
        timing={"start_day": 0, "end_day": 10, "delay_reduction_days": 2},
    )
    result = effects.apply_decision([10.0] * HORIZON, _schedule(), 80.0, decision, HORIZON)
    moved = [entry for entry in result["schedule"] if entry.get("expedited")]
    assert len(moved) == 1
    assert moved[0]["day_offset"] == 0
    assert moved[0]["quantity"] == 60.0
    remaining = [entry for entry in result["schedule"] if not entry.get("expedited")]
    assert sum(entry["quantity"] for entry in remaining) == 90.0
    with pytest.raises(ValueError, match="must be > 0"):
        effects.apply_decision(
            [10.0] * HORIZON, _schedule(), 80.0,
            _decision("EXPEDITE_INBOUND", quantities={"expedite_units": 0.0},
                      timing={"delay_reduction_days": 2}),
            HORIZON,
        )


def test_alternative_supplier_reattributes():
    decision = _decision("ALTERNATIVE_SUPPLIER", affected_suppliers=["S2"])
    result = effects.apply_decision([10.0] * HORIZON, _schedule(), 80.0, decision, HORIZON)
    assert {entry["supplier_id"] for entry in result["schedule"]} == {"S2"}
    assert sum(entry["quantity"] for entry in result["schedule"]) == 150.0
    with pytest.raises(ValueError, match="explicit affected_suppliers"):
        effects.apply_decision(
            [10.0] * HORIZON, _schedule(), 80.0,
            decisions.build_decision("R1", "ALTERNATIVE_SUPPLIER"), HORIZON,
        )


def test_supplier_allocation_splits_proportionally():
    decision = _decision(
        "SUPPLIER_ALLOCATION_CHANGE",
        affected_suppliers=["S1", "S2"],
        quantities={"S1": 60.0, "S2": 40.0},
    )
    result = effects.apply_decision([10.0] * HORIZON, _schedule(), 80.0, decision, HORIZON)
    by_supplier: dict[str, float] = {}
    for entry in result["schedule"]:
        by_supplier[entry["supplier_id"]] = by_supplier.get(entry["supplier_id"], 0.0) + entry["quantity"]
    assert by_supplier == {"S1": 90.0, "S2": 60.0}
    with pytest.raises(ValueError, match="explicit allocation"):
        effects.apply_decision(
            [10.0] * HORIZON, _schedule(), 80.0,
            decisions.build_decision("R1", "SUPPLIER_ALLOCATION_CHANGE",
                                     affected_suppliers=["S1"]),
            HORIZON,
        )


def test_inventory_transfer_conservation():
    decision = _decision(
        "INVENTORY_TRANSFER",
        affected_products=["P1"], affected_warehouses=["W1", "W2"],
        quantities={"transfer_units": 30.0},
    )
    result = effects.apply_transfer_pair(
        {("P1", "W1"): [10.0] * HORIZON},
        {("P1", "W1"): 100.0, ("P1", "W2"): 20.0},
        decision,
    )
    assert result["on_hand_by_key"] == {("P1", "W1"): 70.0, ("P1", "W2"): 50.0}
    assert "Conservation holds" in result["notes"][0]


def test_demand_adjustment_scales_window():
    decision = _decision(
        "DEMAND_ADJUSTMENT",
        quantities={"demand_multiplier": 1.5},
        timing={"start_day": 2, "end_day": 4},
    )
    result = effects.apply_decision([10.0] * HORIZON, _schedule(), 80.0, decision, HORIZON)
    assert result["demand"] == [10.0, 10.0, 15.0, 15.0] + [10.0] * 6
    assert "not a forecast" in result["notes"][0]
    with pytest.raises(ValueError, match="positive"):
        effects.apply_decision(
            [10.0] * HORIZON, _schedule(), 80.0,
            _decision("DEMAND_ADJUSTMENT", quantities={"demand_multiplier": 0.0}),
            HORIZON,
        )


def test_purchase_order_adjustment_adds_inbound():
    decision = _decision(
        "PURCHASE_ORDER_ADJUSTMENT",
        quantities={"order_units": 75.0},
        timing={"arrival_day": 3},
    )
    result = effects.apply_decision([10.0] * HORIZON, _schedule(), 80.0, decision, HORIZON)
    modeled = [entry for entry in result["schedule"] if entry.get("modeled")]
    assert len(modeled) == 1
    assert modeled[0]["quantity"] == 75.0 and modeled[0]["day_offset"] == 3
    with pytest.raises(ValueError, match="outside"):
        effects.apply_decision(
            [10.0] * HORIZON, _schedule(), 80.0,
            _decision("PURCHASE_ORDER_ADJUSTMENT",
                      quantities={"order_units": 75.0},
                      timing={"arrival_day": 99}),
            HORIZON,
        )


def test_combined_action_order_and_nesting():
    decision = decisions.build_decision(
        "R1", "COMBINED_ACTION",
        components=[
            decisions.build_decision(
                "R1", "DEMAND_ADJUSTMENT",
                quantities={"demand_multiplier": 2.0},
                timing={"start_day": 0, "end_day": 10},
            ),
            decisions.build_decision(
                "R1", "PURCHASE_ORDER_ADJUSTMENT",
                affected_suppliers=["S1"],
                quantities={"order_units": 25.0},
                timing={"arrival_day": 1},
            ),
        ],
    )
    result = effects.apply_decision([10.0] * HORIZON, _schedule(), 80.0, decision, HORIZON)
    assert result["demand"] == [20.0] * HORIZON
    assert any(entry.get("modeled") for entry in result["schedule"])
    assert result["notes"][0].startswith("COMBINED_ACTION")
    with pytest.raises(ValueError, match="cannot nest"):
        effects.apply_decision(
            [10.0] * HORIZON, _schedule(), 80.0,
            decisions.build_decision(
                "R1", "COMBINED_ACTION",
                components=[decisions.build_decision(
                    "R1", "COMBINED_ACTION",
                    components=[decisions.build_decision("R1", "NO_ACTION")],
                )],
            ),
            HORIZON,
        )


def test_copy_on_write_inputs_untouched():
    demand = [10.0] * HORIZON
    schedule = _schedule()
    snapshot_demand = list(demand)
    snapshot_schedule = [dict(entry) for entry in schedule]
    decision = _decision(
        "EXPEDITE_INBOUND",
        quantities={"expedite_units": 60.0},
        timing={"start_day": 0, "end_day": 10, "delay_reduction_days": 2},
    )
    effects.apply_decision(demand, schedule, 80.0, decision, HORIZON)
    assert demand == snapshot_demand
    assert schedule == snapshot_schedule
    with pytest.raises(ValueError, match="Unknown decision type"):
        effects.apply_decision(
            demand, schedule, 80.0,
            decisions.Decision(decision_id="x", decision_type="NOPE"), HORIZON,
        )
