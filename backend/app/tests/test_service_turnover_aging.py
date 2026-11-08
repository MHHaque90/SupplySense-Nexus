"""Phase 5 service, turnover, aging, anomaly, and concentration tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory import aging, anomalies, concentration, service, turnover
from backend.app.analytics.inventory.types import DEFAULT_INVENTORY_CONFIG

CONFIG = DEFAULT_INVENTORY_CONFIG


def _snapshots():
    return pd.DataFrame({
        "product_id": ["P1"] * 5 + ["P2"] * 2,
        "warehouse_id": ["W1"] * 7,
        "snapshot_date": [
            date(2026, 6, d) for d in (1, 10, 20, 25, 30) + (15, 30)
        ],
        "on_hand": [100.0, 90.0, 0.0, 0.0, 60.0, 40.0, 50.0],
    })


def _transactions():
    return pd.DataFrame({
        "product_id": ["P1"] * 5,
        "warehouse_id": ["W1"] * 5,
        "timestamp": [date(2026, 6, d) for d in (2, 11, 21, 26, 28)],
        "transaction_type": ["RECEIPT", "SALE", "SALE", "ADJUSTMENT", "SALE"],
        "quantity": [60.0, 30.0, 40.0, 150.0, 10.0],
    })


def test_service_warning_repeated_stockouts():
    warned, text = service.service_warning("P1", "W1", _snapshots())
    assert warned is True
    assert "2 stockout" in text
    warned, _ = service.service_warning("P2", "W1", _snapshots())
    assert warned is False


def test_service_warning_missing_history():
    warned, text = service.service_warning("PX", "W1", _snapshots())
    assert warned is False
    assert "No snapshot history" in text


def test_turnover_proxy_and_trend():
    stats = turnover.series_turnover("P1", "W1", _transactions(), _snapshots())
    assert stats["sales"] == 80.0
    assert stats["turnover_proxy"] == 80.0 / ((100 + 90 + 0 + 0 + 60) / 5)
    trend = turnover.turnover_trend("P1", "W1", _transactions(), _snapshots(), split_days=30)
    assert set(trend) == {"early", "recent"}
    missing = turnover.series_turnover("PX", "W1", _transactions(), _snapshots())
    assert missing["turnover_proxy"] is None


def test_aging_reports_movement_not_lot_age():
    result = aging.days_since_movement("P1", "W1", _transactions(), date(2026, 6, 30))
    assert result["days_since_movement"] == 2
    assert "not lot age" in result["note"]
    missing = aging.days_since_movement("PX", "W1", _transactions(), date(2026, 6, 30))
    assert missing["days_since_movement"] is None


def test_anomaly_rules_fire_with_evidence():
    found = anomalies.detect_anomalies(
        "P1", "W1", _snapshots(), _transactions(), date(2026, 6, 30), CONFIG
    )
    rules = {anomaly.rule for anomaly in found}
    assert "sudden_drop" in rules  # 90 -> 0 on 2026-06-20
    assert "large_adjustment" in rules  # 150 >= 100
    for anomaly in found:
        assert anomaly.product_id == "P1" and anomaly.warehouse_id == "W1"
        assert anomaly.severity in ("info", "watch", "high")
        assert anomaly.explanation


def test_negative_inventory_anomaly():
    frames = _snapshots().copy()
    frames.loc[len(frames)] = ["P1", "W1", date(2026, 6, 30), -5.0]
    found = anomalies.detect_anomalies(
        "P1", "W1", frames, _transactions(), date(2026, 6, 30), CONFIG
    )
    assert any(a.rule == "negative_inventory" and a.severity == "high" for a in found)


def test_no_movement_anomaly():
    old_txns = _transactions().copy()
    old_txns["timestamp"] = date(2026, 1, 1)
    found = anomalies.detect_anomalies(
        "P1", "W1", _snapshots(), old_txns, date(2026, 6, 30), CONFIG
    )
    assert any(a.rule == "no_movement" for a in found)


def test_concentration_shares():
    by_warehouse = concentration.concentration_by_warehouse(_snapshots())
    assert abs(sum(row["share"] for row in by_warehouse) - 1.0) < 1e-9
    by_product = concentration.concentration_by_product(_snapshots(), top_n=1)
    assert len(by_product) == 1
    assert by_product[0]["product_id"] == "P1"
    assert concentration.concentration_by_warehouse(pd.DataFrame()) == []
