"""Phase 3 service and procurement KPI tests."""

from datetime import date

import pandas as pd

from backend.app.analytics.kpis import procurement_kpis, service_kpis


def _sales_orders():
    return pd.DataFrame({
        "order_id": ["O1", "O2", "O3", "O4"],
        "order_date": [date(2026, 1, 1)] * 4,
        "warehouse_id": ["W1"] * 4,
        "status": ["fulfilled", "fulfilled", "partially_fulfilled", "fulfilled"],
    })


def _purchase_orders():
    return pd.DataFrame({
        "po_id": ["PO1", "PO2"],
        "supplier_id": ["S1", "S2"],
        "product_id": ["P1", "P1"],
        "order_date": [date(2026, 1, 1), date(2026, 1, 5)],
        "expected_delivery_date": [date(2026, 1, 10), date(2026, 1, 12)],
        "quantity": [100.0, 50.0],
        "unit_cost": [10.0, 12.0],
        "line_total": [1000.0, 600.0],
        "moq": [25.0, 100.0],
        "lead_time_days": [9, 7],
        "status": ["received", "ordered"],
    })


def _shipments():
    return pd.DataFrame({
        "shipment_id": ["SH1", "SH2", "SH3"],
        "po_id": ["PO1", "PO1", "PO2"],
        "supplier_id": ["S1", "S1", "S2"],
        "shipped_date": [date(2026, 1, 2)] * 3,
        "expected_arrival_date": [date(2026, 1, 10)] * 3,
        "actual_arrival_date": [date(2026, 1, 9), date(2026, 1, 12), None],
        "status": ["delivered", "delivered", "in_transit"],
        "delay_days": [-1.0, 2.0, float("nan")],
    })


def test_order_fulfillment_rate_documents_denominator():
    result = service_kpis.order_fulfillment_rate(_sales_orders(), pd.DataFrame())[0]
    assert result.value == 0.75
    assert result.numerator == 3.0
    assert result.denominator == 4.0
    assert "proxy" in result.notes.lower()


def test_demand_fulfillment_rate():
    demand = pd.DataFrame({"date": [date(2026, 1, 1)], "quantity": [200.0]})
    lines = pd.DataFrame({"quantity": [150.0]})
    result = service_kpis.demand_fulfillment_rate(demand, lines)[0]
    assert result.value == 0.75
    assert service_kpis.demand_fulfillment_rate(pd.DataFrame(), lines)[0].value is None


def test_procurement_summary_and_lead_times():
    stats = {k.metric_name: k.value
             for k in procurement_kpis.procurement_summary(_purchase_orders())}
    assert stats["purchase_order_count"] == 2.0
    assert stats["ordered_quantity"] == 150.0
    assert stats["ordered_spend"] == 1600.0
    leads = {k.metric_name: k.value
             for k in procurement_kpis.lead_time_stats(_purchase_orders())}
    assert leads["average_contracted_lead_time"] == 8.0
    assert leads["average_realized_lead_time"] == 8.0


def test_shipment_performance_denominator_is_delivered():
    stats = {k.metric_name: k.value
             for k in procurement_kpis.shipment_performance(_shipments())}
    assert stats["on_time_shipment_rate"] == 0.5
    assert stats["late_shipment_rate"] == 0.5
    assert stats["average_shipment_delay"] == 0.5
    assert procurement_kpis.shipment_performance(pd.DataFrame()) == []


def test_moq_compliance():
    result = procurement_kpis.moq_compliance(_purchase_orders())[0]
    assert result.value == 0.5  # PO2 line of 50 < MOQ 100
    assert result.denominator == 2.0


def test_concentration_is_descriptive():
    stats = {k.metric_name: k.value
             for k in procurement_kpis.concentration(_purchase_orders())}
    assert stats["top_supplier_spend_share"] == 1000 / 1600
    assert abs(stats["supplier_hhi"] - ((1000 / 1600) ** 2 + (600 / 1600) ** 2)) < 1e-9
