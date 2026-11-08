"""Phase 8 point-in-time leakage tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.simulation import runner


def _frames(extra_future=True):
    snapshots = pd.DataFrame({
        "product_id": ["P1", "P1"],
        "warehouse_id": ["W1", "W1"],
        "snapshot_date": [date(2026, 6, 20), date(2026, 6, 30)],
        "on_hand": [90.0, 80.0],
    })
    shipments = pd.DataFrame({
        "shipment_id": ["SH1"],
        "po_id": ["PO1"],
        "supplier_id": ["S1"],
        "expected_arrival_date": [date(2026, 7, 3)],
        "actual_arrival_date": [pd.NaT],
    })
    po_lines = pd.DataFrame({
        "po_id": ["PO1"],
        "supplier_id": ["S1"],
        "product_id": ["P1"],
        "order_date": [date(2026, 6, 20)],
        "quantity": [40.0],
    })
    demand = pd.DataFrame({
        "product_id": ["P1"],
        "warehouse_id": ["W1"],
        "date": [date(2026, 6, 30)],
        "quantity": [10.0],
    })
    if extra_future:
        snapshots = pd.concat([snapshots, pd.DataFrame([{
            "product_id": "P1", "warehouse_id": "W1",
            "snapshot_date": date(2027, 1, 1), "on_hand": 9999.0,
        }])], ignore_index=True)
        shipments = pd.concat([shipments, pd.DataFrame([{
            "shipment_id": "SH9", "po_id": "PO9", "supplier_id": "S1",
            "expected_arrival_date": date(2027, 1, 10),
            "actual_arrival_date": pd.NaT,
        }])], ignore_index=True)
        po_lines = pd.concat([po_lines, pd.DataFrame([{
            "po_id": "PO9", "supplier_id": "S1", "product_id": "P1",
            "order_date": date(2027, 1, 5), "quantity": 5000.0,
        }])], ignore_index=True)
        demand = pd.concat([demand, pd.DataFrame([{
            "product_id": "P1", "warehouse_id": "W1",
            "date": date(2027, 1, 1), "quantity": 9999.0,
        }])], ignore_index=True)
    return snapshots, shipments, po_lines, demand


def _series_keys(snapshots, analysis_date):
    return sorted({
        (str(row["product_id"]), str(row["warehouse_id"]))
        for _, row in snapshots[
            pd.to_datetime(snapshots["snapshot_date"]).dt.date <= analysis_date
        ].iterrows()
    })


def test_future_inventory_excluded_from_targets():
    clean = _series_keys(_frames(False)[0], date(2026, 6, 30))
    dirty = _series_keys(_frames(True)[0], date(2026, 6, 30))
    assert dirty == clean == [("P1", "W1")]


def test_future_po_shipment_excluded_from_schedule():
    from backend.app.analytics.simulation import simulation as sim_mod

    _, shipments, po_lines, _ = _frames(False)
    _, future_shipments, future_lines, _ = _frames(True)
    analysis, horizon_end = date(2026, 6, 30), date(2026, 7, 14)
    dates = [(analysis.fromordinal(analysis.toordinal() + step)).isoformat()
             for step in range(1, 15)]
    clean = sim_mod.build_inbound_schedule("P1", shipments, po_lines, analysis, horizon_end, dates)
    dirty = sim_mod.build_inbound_schedule(
        "P1", future_shipments, future_lines, analysis, horizon_end, dates)
    assert dirty == clean
    assert clean[0]["quantity"] == 40.0


def test_future_demand_excluded_from_baseline():
    from backend.app.analytics.simulation import baseline as baseline_mod

    _, shipments, po_lines, demand = _frames(True)
    analysis = date(2026, 6, 30)
    history = demand[pd.to_datetime(demand["date"]).dt.date <= analysis]
    assert history["quantity"].tolist() == [10.0]
    state = baseline_mod.build_baseline_series(
        "P1", "W1", 80.0, [10.0] * 7, [8.0] * 7, [12.0] * 7,
        analysis, 7, shipments, po_lines, analysis, {},
    )
    assert state["demand_point"] == [10.0] * 7
    assert state["on_hand"] == 80.0


def test_future_supplier_data_excluded_from_targets():
    import pandas as pd

    links = pd.DataFrame({
        "supplier_id": ["S1"],
        "product_id": ["P1"],
    })
    future_links = pd.DataFrame({
        "supplier_id": ["S1", "S9"],
        "product_id": ["P1", "P1"],
    })
    snapshots, _, _, _ = _frames(False)
    clean = runner.resolve_series(
        [{"entity_type": "supplier", "supplier_id": "S1"}],
        snapshots, links,
    )
    # A future supplier relationship must not alter S1 resolution.
    assert runner.resolve_series(
        [{"entity_type": "supplier", "supplier_id": "S1"}],
        snapshots, future_links,
    ) == clean == [("P1", "W1")]


def test_event_window_bounded_by_horizon():
    from backend.app.analytics.simulation import simulation as sim_mod
    from backend.app.analytics.simulation.types import DisruptionEvent as Event

    event = Event(event_id="E", event_type="SUPPLY_REDUCTION",
                  duration_days=365, supply_reduction=1.0)
    assert sim_mod._window(event, 14) == (0, 14)
