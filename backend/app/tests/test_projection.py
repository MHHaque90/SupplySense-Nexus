"""Phase 5 projection tests: depletion, receipts, crossings."""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory import projection
from backend.app.analytics.inventory.types import ForecastInput


def _forecast(point):
    total = len(point)
    return ForecastInput(
        product_id="P1", warehouse_id="W1", origin="2026-06-30",
        forecast_dates=[f"2026-07-{day:02d}" for day in range(1, total + 1)],
        horizon=total, point=list(point),
        lower=list(point), upper=list(point),
    )


def test_demand_depletion_without_receipts():
    trajectory = projection.project_trajectory(25.0, _forecast([10.0, 10.0, 10.0]))
    assert [point.projected_ending for point in trajectory] == [15.0, 5.0, -5.0]
    assert [point.projected_stockout for point in trajectory] == [False, False, True]
    assert trajectory[0].beginning_inventory == 25.0
    assert trajectory[0].known_inbound == 0.0


def test_known_receipts_offset_depletion():
    trajectory = projection.project_trajectory(
        15.0, _forecast([10.0, 10.0]), {"2026-07-02": 12.0}
    )
    assert [point.projected_ending for point in trajectory] == [5.0, 7.0]
    assert not any(point.projected_stockout for point in trajectory)


def test_no_stockout_when_covered():
    trajectory = projection.project_trajectory(100.0, _forecast([5.0] * 5))
    assert not any(point.projected_stockout for point in trajectory)
    assert trajectory[-1].projected_ending == 75.0


def test_known_inbound_from_pending_shipments():
    shipments = pd.DataFrame({
        "shipment_id": ["S1", "S2", "S3"],
        "po_id": ["PO1", "PO1", "PO2"],
        "expected_arrival_date": [date(2026, 7, 3), date(2026, 7, 5), date(2026, 6, 1)],
        "actual_arrival_date": [None, None, date(2026, 6, 1)],
    })
    po_lines = pd.DataFrame({
        "po_id": ["PO1", "PO2"],
        "product_id": ["P1", "P1"],
        "quantity": [40.0, 99.0],
    })
    inbound = projection.known_inbound(
        "P1", shipments, po_lines, date(2026, 6, 30), date(2026, 7, 10)
    )
    # PO1 contributes once at its earliest in-window arrival; delivered PO2 ignored.
    assert inbound == {"2026-07-03": 40.0}
    assert projection.known_inbound("P9", shipments, po_lines, date(2026, 6, 30), date(2026, 7, 10)) == {}


def test_no_future_receipts_without_evidence():
    assert projection.known_inbound(
        "P1", pd.DataFrame(), pd.DataFrame(), date(2026, 6, 30), date(2026, 7, 10)
    ) == {}
    trajectory = projection.project_trajectory(8.0, _forecast([5.0, 5.0]))
    assert trajectory[1].projected_stockout is True
