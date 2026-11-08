"""Phase 8 deterministic engine mechanics tests."""

import numpy as np
import pytest

from backend.app.analytics.simulation import inventory_engine
from backend.app.analytics.simulation.simulation import run_baseline_once, run_entity_once
from backend.app.analytics.simulation.types import DisruptionEvent


def _event(**overrides):
    params = {
        "event_id": "E1", "event_type": "SUPPLY_REDUCTION", "name": "Cut",
        "duration_days": 14, "supply_reduction": 0.5,
    }
    params.update(overrides)
    return DisruptionEvent(**params)


def test_inventory_depletion_and_unmet():
    result = inventory_engine.run_days(25.0, np.array([10.0, 10.0, 10.0]), np.zeros(3))
    assert result["ending"].tolist() == [15.0, 5.0, 0.0]
    assert result["unmet"].tolist() == [0.0, 0.0, 5.0]
    assert result["stockout_flag"].tolist() == [False, False, True]
    assert inventory_engine.first_stockout_day(result["stockout_flag"]) == 2
    assert inventory_engine.first_stockout_day(np.zeros(3, dtype=bool)) is None


def test_inbound_arrival_offsets_depletion():
    arrivals = [{"day_offset": 1, "quantity": 12.0, "supplier_id": "S1"}]
    result = run_baseline_once(15.0, [10.0, 10.0], arrivals, 2)
    assert result["ending"].tolist() == [5.0, 7.0]
    assert result["unmet"].tolist() == [0.0, 0.0]


def test_delayed_inbound_shifts_arrivals():
    from backend.app.analytics.simulation import supply_effects

    arrivals = np.array([0.0, 40.0, 0.0])
    shifted, info = supply_effects.apply_arrival_delay(arrivals, 1, 0, 3)
    assert shifted.tolist() == [0.0, 0.0, 40.0]
    assert info["delayed_inbound_quantity"] == 40.0
    with pytest.raises(ValueError):
        supply_effects.apply_arrival_delay(arrivals, -1, 0, 3)


def test_stockout_semantics():
    # ending <= 0 with positive demand flags; zero demand never flags.
    result = inventory_engine.run_days(0.0, np.array([0.0, 0.0]), np.zeros(2))
    assert result["stockout_flag"].tolist() == [False, False]
    assert result["unmet"].tolist() == [0.0, 0.0]
    with pytest.raises(ValueError):
        inventory_engine.run_days(10.0, np.array([1.0]), np.zeros(2))


def test_unmet_demand_tracked_separately():
    result = inventory_engine.run_days(5.0, np.array([8.0, 8.0]), np.zeros(2))
    assert result["ending"].tolist() == [0.0, 0.0]
    assert result["unmet"].tolist() == [3.0, 8.0]


def test_demand_shock_scales_window_only():
    event = _event(event_type="DEMAND_SHOCK", demand_multiplier=2.0, duration_days=2)
    arrivals = [{"day_offset": 0, "quantity": 0.0, "supplier_id": None}]
    result = run_entity_once(100.0, [10.0, 10.0, 10.0, 10.0], arrivals, 4, event, {})
    assert result["unmet"].tolist() == [0.0, 0.0, 0.0, 0.0]
    assert result["ending"].tolist() == [80.0, 60.0, 50.0, 40.0]


def test_supply_reduction_removes_inbound():
    event = _event(event_type="SUPPLY_REDUCTION", supply_reduction=1.0, duration_days=3)
    arrivals = [{"day_offset": 1, "quantity": 30.0, "supplier_id": "S1"}]
    result = run_entity_once(5.0, [10.0, 10.0, 10.0], arrivals, 3, event, {})
    assert result["ending"].tolist() == [0.0, 0.0, 0.0]
    assert result["unmet"].tolist() == [5.0, 10.0, 10.0]


def test_warehouse_unavailability_preserves_balance():
    event = _event(event_type="WAREHOUSE_DISRUPTION", duration_days=2,
                   affected_warehouses=["W1"], warehouse_available=False)
    arrivals = [{"day_offset": 0, "quantity": 0.0, "supplier_id": None}]
    result = run_entity_once(50.0, [10.0, 10.0, 10.0], arrivals, 3, event, {})
    assert result["ending"].tolist() == [50.0, 50.0, 40.0]
    assert result["unmet"].tolist() == [10.0, 10.0, 0.0]
    assert result["stockout_flag"].tolist() == [True, True, False]
