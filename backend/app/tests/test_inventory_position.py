"""Phase 5 inventory position tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory import position
from backend.app.analytics.inventory.types import DEFAULT_INVENTORY_CONFIG

ANALYSIS = date(2026, 6, 30)


def _snapshots():
    return pd.DataFrame({
        "product_id": ["P1"] * 4 + ["P2"] * 2,
        "warehouse_id": ["W1"] * 6,
        "snapshot_date": [
            date(2026, 6, 1), date(2026, 6, 10), date(2026, 6, 20), date(2026, 6, 30),
            date(2026, 6, 15), date(2026, 6, 30),
        ],
        "on_hand": [100.0, 80.0, 0.0, 60.0, 40.0, 50.0],
    })


def _transactions():
    return pd.DataFrame({
        "product_id": ["P1"] * 4,
        "warehouse_id": ["W1"] * 4,
        "timestamp": [date(2026, 6, d) for d in (5, 12, 21, 25)],
        "transaction_type": ["RECEIPT", "SALE", "SALE", "ADJUSTMENT"],
        "quantity": [50.0, 30.0, 40.0, 5.0],
    })


def test_latest_inventory_uses_latest_snapshot():
    result = position.describe_position(
        "P1", "W1", _snapshots(), _transactions(), ANALYSIS, DEFAULT_INVENTORY_CONFIG
    )
    assert result.current_on_hand == 60.0
    assert result.latest_snapshot_date == "2026-06-30"
    assert not result.unknown


def test_position_statistics_and_movement():
    result = position.describe_position(
        "P1", "W1", _snapshots(), _transactions(), ANALYSIS, DEFAULT_INVENTORY_CONFIG
    )
    assert result.recent_minimum == 0.0
    assert result.recent_maximum == 100.0
    assert result.recent_average == 60.0
    assert result.recent_inflow == 55.0
    assert result.recent_outflow == 70.0
    assert result.adjustment_count == 1
    assert result.stockout_observations == 1


def test_warehouses_stay_separate():
    frames = _snapshots()
    result = position.describe_position(
        "P1", "W2", frames, _transactions(), ANALYSIS, DEFAULT_INVENTORY_CONFIG
    )
    assert result.unknown and result.current_on_hand is None


def test_unknown_position_without_snapshots():
    result = position.describe_position(
        "PX", "W1", _snapshots(), _transactions(), ANALYSIS, DEFAULT_INVENTORY_CONFIG
    )
    assert result.unknown
    assert result.latest_snapshot_date is None


def test_point_in_time_discipline():
    # Snapshots after the analysis date must not leak into the position.
    future = _snapshots().copy()
    future.loc[len(future)] = ["P1", "W1", date(2026, 7, 15), 9999.0]
    result = position.describe_position(
        "P1", "W1", future, _transactions(), ANALYSIS, DEFAULT_INVENTORY_CONFIG
    )
    assert result.current_on_hand == 60.0
    assert result.latest_snapshot_date == "2026-06-30"


def test_future_perturbation_does_not_change_position():
    base = position.describe_position(
        "P1", "W1", _snapshots(), _transactions(), ANALYSIS, DEFAULT_INVENTORY_CONFIG
    )
    tampered = _snapshots().copy()
    tampered.loc[len(tampered)] = ["P1", "W1", date(2026, 12, 31), 1.0]
    tampered_txns = _transactions().copy()
    tampered_txns.loc[len(tampered_txns)] = ["P1", "W1", date(2026, 12, 31), "SALE", 1.0]
    changed = position.describe_position(
        "P1", "W1", tampered, tampered_txns, ANALYSIS, DEFAULT_INVENTORY_CONFIG
    )
    assert changed.to_dict() == base.to_dict()
