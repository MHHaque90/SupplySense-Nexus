"""Phase 9 descriptive constraint-check tests (no optimizer)."""

import pandas as pd
import pytest

from backend.app.analytics.replay import constraints, decisions


def _links():
    return pd.DataFrame({
        "supplier_id": ["S1", "S2"],
        "product_id": ["P1", "P2"],
        "min_order_qty": ["25", "10"],
        "capacity_units": ["1000", None],
        "lead_time_days": ["7", "14"],
    })


def _warehouses():
    return pd.DataFrame({
        "id": ["W1", "W2"],
        "capacity_units": ["5000", None],
    })


def _on_hand():
    return {("P1", "W1"): 100.0}


def _decision(**overrides):
    params = {
        "affected_suppliers": ["S1"], "affected_products": ["P1"],
        "affected_warehouses": ["W1"],
        "quantities": {"order_units": 50.0},
        "timing": {"start_day": 0, "end_day": 7},
    }
    params.update(overrides)
    return decisions.build_decision("R1", "PURCHASE_ORDER_ADJUSTMENT", **params)


def test_moq_pass_and_fail():
    notes = constraints.check_constraints(_decision(), _links(), _warehouses(), _on_hand(), 28)
    assert any("meets MOQ 25" in note for note in notes)
    with pytest.raises(ValueError, match="below MOQ"):
        constraints.check_constraints(
            _decision(quantities={"order_units": 5.0}),
            _links(), _warehouses(), _on_hand(), 28,
        )


def test_supplier_capacity_checked_or_unchecked():
    notes = constraints.check_constraints(_decision(), _links(), _warehouses(), _on_hand(), 28)
    assert any("capacity recorded for S1" in note for note in notes)
    decision = _decision(affected_suppliers=["S2"], affected_products=["P2"],
                         quantities={"order_units": 20.0})
    notes = constraints.check_constraints(decision, _links(), _warehouses(), _on_hand(), 28)
    assert any("UNCHECKED: supplier capacity unavailable for S2" in note for note in notes)


def test_warehouse_capacity_checked_or_unchecked():
    notes = constraints.check_constraints(_decision(), _links(), _warehouses(), _on_hand(), 28)
    assert any("capacity recorded for W1" in note for note in notes)
    assert any("UNCHECKED: warehouse capacity unavailable for W2" in note
               for note in constraints.check_constraints(
                   _decision(affected_warehouses=["W2"]),
                   _links(), _warehouses(), _on_hand(), 28))


def test_available_inventory_noted():
    notes = constraints.check_constraints(_decision(), _links(), _warehouses(), _on_hand(), 28)
    assert isinstance(notes, list) and notes


def test_supplier_product_link_check():
    notes = constraints.check_constraints(_decision(), _links(), _warehouses(), _on_hand(), 28)
    assert any("relationship S1|P1 exists" in note for note in notes)
    with pytest.raises(ValueError, match="does not supply"):
        constraints.check_constraints(
            _decision(affected_suppliers=["S9"]), _links(), _warehouses(), _on_hand(), 28
        )
    with pytest.raises(ValueError, match="FAIL:"):
        constraints.check_constraints(
            decisions.build_decision(
                "R1", "ALTERNATIVE_SUPPLIER",
                affected_suppliers=["S2"], affected_products=["P1"],
                quantities={"switch_units": 10.0},
            ),
            _links(), _warehouses(), _on_hand(), 28,
        )


def test_lead_time_evidence_noted():
    notes = constraints.check_constraints(_decision(), _links(), _warehouses(), _on_hand(), 28)
    assert any("lead-time evidence available" in note for note in notes)
    no_lead = pd.DataFrame({
        "supplier_id": ["S1"], "product_id": ["P1"],
        "min_order_qty": ["25"], "capacity_units": ["1000"],
    })
    notes = constraints.check_constraints(_decision(), no_lead, _warehouses(), _on_hand(), 28)
    assert any("UNCHECKED: lead-time evidence unavailable" in note for note in notes)


def test_timing_window_noted():
    notes = constraints.check_constraints(_decision(), _links(), _warehouses(), _on_hand(), 28)
    assert any("timing window" in note for note in notes)
