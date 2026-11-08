"""Phase 5 temporal leakage tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory import position, reports
from backend.app.analytics.inventory.types import DEFAULT_INVENTORY_CONFIG

ANALYSIS = date(2026, 6, 30)


def _frames(extra_future=True):
    snapshots = pd.DataFrame({
        "product_id": ["P1"] * 3,
        "warehouse_id": ["W1"] * 3,
        "snapshot_date": [date(2026, 6, 10), date(2026, 6, 20), date(2026, 6, 30)],
        "on_hand": [100.0, 80.0, 60.0],
    })
    transactions = pd.DataFrame({
        "product_id": ["P1"] * 2,
        "warehouse_id": ["W1"] * 2,
        "timestamp": [date(2026, 6, 12), date(2026, 6, 22)],
        "transaction_type": ["SALE", "SALE"],
        "quantity": [20.0, 20.0],
    })
    if extra_future:
        future_snaps = pd.DataFrame({
            "product_id": ["P1"],
            "warehouse_id": ["W1"],
            "snapshot_date": [date(2026, 12, 31)],
            "on_hand": [9999.0],
        })
        future_txns = pd.DataFrame({
            "product_id": ["P1"],
            "warehouse_id": ["W1"],
            "timestamp": [date(2026, 12, 31)],
            "transaction_type": ["RECEIPT"],
            "quantity": [9999.0],
        })
        snapshots = pd.concat([snapshots, future_snaps], ignore_index=True)
        transactions = pd.concat([transactions, future_txns], ignore_index=True)
    return snapshots, transactions


def test_position_ignores_future_observations():
    clean_snaps, clean_txns = _frames(extra_future=False)
    dirty_snaps, dirty_txns = _frames(extra_future=True)
    clean = position.describe_position(
        "P1", "W1", clean_snaps, clean_txns, ANALYSIS, DEFAULT_INVENTORY_CONFIG
    )
    dirty = position.describe_position(
        "P1", "W1", dirty_snaps, dirty_txns, ANALYSIS, DEFAULT_INVENTORY_CONFIG
    )
    assert dirty.to_dict() == clean.to_dict()


def test_intelligence_result_stable_under_future_perturbation():
    from backend.app.analytics.inventory.types import ForecastInput

    clean_snaps, clean_txns = _frames(extra_future=False)
    dirty_snaps, dirty_txns = _frames(extra_future=True)
    demand = pd.DataFrame({
        "product_id": ["P1"] * 3,
        "warehouse_id": ["W1"] * 3,
        "date": [date(2026, 6, 10), date(2026, 6, 20), date(2026, 6, 30)],
        "quantity": [10.0, 10.0, 10.0],
    })
    forecast = ForecastInput(
        product_id="P1", warehouse_id="W1", origin="2026-06-30",
        forecast_dates=["2026-07-01", "2026-07-02"],
        horizon=2, point=[10.0, 10.0], lower=[8.0, 8.0], upper=[12.0, 12.0],
    )
    shipments = pd.DataFrame()
    po_lines = pd.DataFrame()
    clean = reports.build_intelligence(
        "P1", "W1", clean_snaps, clean_txns, demand, forecast,
        shipments, po_lines, ANALYSIS, DEFAULT_INVENTORY_CONFIG,
    )
    dirty = reports.build_intelligence(
        "P1", "W1", dirty_snaps, dirty_txns, demand, forecast,
        shipments, po_lines, ANALYSIS, DEFAULT_INVENTORY_CONFIG,
    )
    assert dirty.to_dict() == clean.to_dict()
