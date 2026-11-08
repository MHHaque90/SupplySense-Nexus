"""Phase 3 inventory KPI tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.kpis import inventory_kpis


def _snapshots():
    return pd.DataFrame({
        "product_id": ["P1", "P1", "P1", "P2", "P2"],
        "warehouse_id": ["W1"] * 5,
        "snapshot_date": [date(2026, 1, d) for d in (1, 2, 3, 1, 2)],
        "on_hand": [100.0, 80.0, 0.0, 50.0, 60.0],
        "reserved": [0.0] * 5,
        "in_transit": [0.0] * 5,
    })


def _transactions():
    return pd.DataFrame({
        "product_id": ["P1"] * 4,
        "warehouse_id": ["W1"] * 4,
        "timestamp": [date(2026, 1, 1)] * 4,
        "transaction_type": ["OPENING_BALANCE", "RECEIPT", "SALE", "ADJUSTMENT"],
        "quantity": [100.0, 20.0, 40.0, 0.0],
    })


def test_current_on_hand_uses_latest_snapshot():
    results = {k.dimensions["product_id"]: k.value
               for k in inventory_kpis.current_on_hand(_snapshots())}
    assert results["P1"] == 0.0
    assert results["P2"] == 60.0


def test_inventory_levels():
    stats = {k.metric_name: k.value for k in inventory_kpis.inventory_levels(_snapshots())}
    assert stats["average_inventory"] == (100 + 80 + 0 + 50 + 60) / 5
    assert stats["minimum_inventory"] == 0.0
    assert stats["maximum_inventory"] == 100.0


def test_stockout_counts():
    stats = {k.metric_name: k.value for k in inventory_kpis.stockout_stats(_snapshots())}
    assert stats["stockout_snapshots"] == 1.0
    assert stats["stockout_rate"] == 1 / 5
    assert stats["zero_inventory_days"] == 1.0


def test_turnover_proxy_and_days_of_supply():
    turnover = inventory_kpis.turnover_proxy(_transactions(), _snapshots())[0]
    assert turnover.value == 40.0 / ((100 + 80 + 0 + 50 + 60) / 5)
    assert "proxy" in turnover.notes.lower()
    supply = inventory_kpis.days_of_supply(_snapshots(), 10.0)[0]
    assert supply.value == ((100 + 80 + 0 + 50 + 60) / 5) / 10.0
    missing = inventory_kpis.days_of_supply(_snapshots(), 0.0)[0]
    assert missing.value is None


def test_movement_summary_signs():
    stats = {k.metric_name: k.value for k in inventory_kpis.movement_summary(_transactions())}
    assert stats["inventory_inflow"] == 120.0
    assert stats["inventory_outflow"] == 40.0
    assert stats["inventory_net_movement"] == 80.0


def test_reconciliation_status():
    txns = pd.DataFrame({
        "product_id": ["P1", "P1", "P1"],
        "warehouse_id": ["W1"] * 3,
        "timestamp": [date(2026, 1, 1)] * 3,
        "transaction_type": ["OPENING_BALANCE", "RECEIPT", "SALE"],
        "quantity": [100.0, 20.0, 30.0],
    })
    snaps = pd.DataFrame({
        "product_id": ["P1", "P1"],
        "warehouse_id": ["W1", "W1"],
        "snapshot_date": [date(2026, 1, 1), date(2026, 1, 2)],
        "on_hand": [100.0, 90.0],
    })
    result = inventory_kpis.reconciliation_status(txns, snaps)[0]
    assert result.value == 1.0
    assert result.denominator == 1.0
    broken = snaps.copy()
    broken.loc[1, "on_hand"] = 10.0
    assert inventory_kpis.reconciliation_status(txns, broken)[0].value == 0.0


def test_kpi_metadata_contract():
    for kpi in inventory_kpis.inventory_levels(_snapshots()):
        payload = kpi.to_dict()
        assert payload["synthetic"] is True
        assert payload["source_tables"] == ["inventory_snapshots"]
        assert payload["time_start"] and payload["time_end"]
        assert payload["numerator"] is None or isinstance(payload["numerator"], float)


def test_empty_frames_return_no_kpis():
    empty = pd.DataFrame()
    assert inventory_kpis.inventory_levels(empty) == []
    assert inventory_kpis.stockout_stats(empty) == []
    assert inventory_kpis.movement_summary(empty) == []
