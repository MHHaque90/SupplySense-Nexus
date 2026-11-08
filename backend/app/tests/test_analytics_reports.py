"""Phase 3 reporting tests: JSON, Markdown, and synthetic labeling."""

from datetime import date

import pandas as pd

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.reports.analytics_report import build_analytics_report, render_markdown


def _frames():
    dates = [date(2026, 1, 1) + pd.Timedelta(days=i) for i in range(120)]
    demand = pd.DataFrame({
        "date": [d for d in dates for _ in range(2)],
        "product_id": ["P1"] * 120 + ["P2"] * 120,
        "warehouse_id": ["W1"] * 240,
        "quantity": [10.0] * 120 + [0.0] * 60 + [20.0] * 60,
    })
    snapshots = pd.DataFrame({
        "product_id": ["P1"] * 4,
        "warehouse_id": ["W1"] * 4,
        "snapshot_date": [date(2026, 1, d) for d in (1, 2, 3, 4)],
        "on_hand": [100.0, 90.0, 80.0, 70.0],
    })
    transactions = pd.DataFrame({
        "product_id": ["P1"] * 3,
        "warehouse_id": ["W1"] * 3,
        "timestamp": [date(2026, 1, 1)] * 3,
        "transaction_type": ["OPENING_BALANCE", "SALE", "SALE"],
        "quantity": [100.0, 20.0, 10.0],
    })
    orders = pd.DataFrame({
        "po_id": ["PO1"], "supplier_id": ["S1"], "product_id": ["P1"],
        "order_date": [date(2026, 1, 1)], "expected_delivery_date": [date(2026, 1, 8)],
        "quantity": [50.0], "unit_cost": [5.0], "line_total": [250.0],
        "moq": [10.0], "lead_time_days": [7], "status": ["received"],
    })
    shipments = pd.DataFrame({
        "shipment_id": ["SH1"], "po_id": ["PO1"], "supplier_id": ["S1"],
        "shipped_date": [date(2026, 1, 2)], "expected_arrival_date": [date(2026, 1, 8)],
        "actual_arrival_date": [date(2026, 1, 8)], "status": ["delivered"],
        "delay_days": [0.0],
    })
    sales_orders = pd.DataFrame({
        "order_id": ["O1"], "order_date": [date(2026, 1, 2)],
        "warehouse_id": ["W1"], "status": ["fulfilled"],
    })
    sales_lines = pd.DataFrame({"quantity": [30.0]})
    return demand, snapshots, transactions, orders, shipments, sales_orders, sales_lines


def test_json_report_structure_and_disclaimer():
    frames = _frames()
    report = build_analytics_report(*frames, AnalyticsConfig(forecast_horizon=14))
    assert report["synthetic"] is True
    assert "SYNTHETIC" in report["disclaimer"]
    assert report["period"] == {"start": "2026-01-01", "end": "2026-04-30"}
    for section in ("demand", "inventory", "procurement", "service"):
        assert section in report
    assert report["demand"]["series_profiled"] == 2
    assert report["forecast_evaluation"] is None  # no series requested
    assert isinstance(report["limitations"], list) and report["limitations"]


def test_report_with_forecast_section():
    frames = _frames()
    demand = frames[0]
    series = demand[demand["product_id"] == "P1"].sort_values("date")
    report = build_analytics_report(
        *frames, AnalyticsConfig(forecast_horizon=14, min_history=60, validation_step=14),
        forecast_series_id="P1|W1",
        forecast_values=series["quantity"].astype(float).tolist(),
    )
    evaluation = report["forecast_evaluation"]
    assert evaluation["series_id"] == "P1|W1"
    assert set(evaluation["model_summary"]) == {"naive", "seasonal_naive", "moving_average", "drift", "ses"}


def test_markdown_uses_analytical_wording():
    frames = _frames()
    report = build_analytics_report(*frames, AnalyticsConfig())
    markdown = render_markdown(report)
    assert markdown.startswith("# SupplySense Nexus Analytics Report")
    assert "SYNTHETIC" in markdown
    assert "synthetic dataset" in markdown
    for banned in ("the company achieved", "the business will", "the supplier will"):
        assert banned not in markdown.lower()
