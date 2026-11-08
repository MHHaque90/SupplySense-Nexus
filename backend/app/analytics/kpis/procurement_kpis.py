"""Procurement KPIs (Phase 3, descriptive foundation only)."""

import pandas as pd

from backend.app.analytics.types import KPIResult

PO_SOURCES = ["purchase_orders", "purchase_order_lines", "supplier_products"]
SHIP_SOURCES = ["shipments"]


def _span(dates: pd.Series) -> tuple[str, str]:
    parsed = pd.to_datetime(dates)
    return str(parsed.min().date()), str(parsed.max().date())


def procurement_summary(orders: pd.DataFrame) -> list[KPIResult]:
    """Count POs, ordered quantities, and spend from line data."""
    if orders.empty:
        return []
    start, end = _span(orders["order_date"])
    ordered_qty = float(orders["quantity"].sum())
    spend = float(pd.to_numeric(orders["line_total"], errors="coerce").fillna(0.0).sum())
    return [
        KPIResult("purchase_order_count", float(len(orders["po_id"].unique())), "count",
                  float(len(orders)), None, start, end, "dataset", {}, PO_SOURCES, True,
                  "formula=count(distinct po_id)", "Observed generated purchase orders."),
        KPIResult("ordered_quantity", ordered_qty, "units", ordered_qty, None,
                  start, end, "dataset", {}, PO_SOURCES, True,
                  "formula=sum(line quantity)", "Observed generated ordered units."),
        KPIResult("ordered_spend", spend, "currency", spend, None, start, end,
                  "dataset", {}, PO_SOURCES, True, "formula=sum(line_total)",
                  "Synthetic monetary total; not real spend."),
    ]


def lead_time_stats(orders: pd.DataFrame) -> list[KPIResult]:
    """Describe contracted and realized lead times in days."""
    if orders.empty:
        return []
    start, end = _span(orders["order_date"])
    contracted = pd.to_numeric(orders["lead_time_days"], errors="coerce").dropna()
    realized = (pd.to_datetime(orders["expected_delivery_date"]) - pd.to_datetime(orders["order_date"])).dt.days
    results = []
    if not contracted.empty:
        results.append(KPIResult(
            "average_contracted_lead_time", float(contracted.mean()), "days",
            None, None, start, end, "dataset", {}, PO_SOURCES, True,
            "formula=mean(supplier lead_time_days)",
            "Contracted terms in generated supplier links."))
    if not realized.empty:
        results.append(KPIResult(
            "average_realized_lead_time", float(realized.mean()), "days",
            None, None, start, end, "dataset", {}, PO_SOURCES, True,
            "formula=mean(expected-order date diff)",
            "Realized schedule in generated purchase orders."))
    return results


def shipment_performance(shipments: pd.DataFrame) -> list[KPIResult]:
    """Compute on-time rate, delay, and late-shipment rate (delivered only)."""
    if shipments.empty:
        return []
    delivered = shipments[shipments["actual_arrival_date"].notna()].copy()
    start, end = _span(shipments["expected_arrival_date"])
    total = len(shipments)
    if delivered.empty:
        return [KPIResult(
            "on_time_shipment_rate", None, "ratio", None, float(total), start, end,
            "dataset", {}, SHIP_SOURCES, True, "formula=on_time/delivered",
            "No delivered shipments in range.")]
    on_time = int((delivered["delay_days"] <= 0).sum())
    late = int((delivered["delay_days"] > 0).sum())
    denom = len(delivered)
    return [
        KPIResult("on_time_shipment_rate", on_time / denom, "ratio", float(on_time),
                  float(denom), start, end, "dataset", {}, SHIP_SOURCES, True,
                  "formula=delay<=0 over delivered",
                  "Denominator is delivered shipments only."),
        KPIResult("late_shipment_rate", late / denom, "ratio", float(late),
                  float(denom), start, end, "dataset", {}, SHIP_SOURCES, True,
                  "formula=delay>0 over delivered", "Denominator is delivered shipments only."),
        KPIResult("average_shipment_delay", float(delivered["delay_days"].mean()), "days",
                  None, None, start, end, "dataset", {}, SHIP_SOURCES, True,
                  "formula=mean(actual-expected)", "Observed generated delays."),
    ]


def moq_compliance(orders: pd.DataFrame) -> list[KPIResult]:
    """Share of PO lines meeting supplier MOQ."""
    if orders.empty:
        return []
    start, end = _span(orders["order_date"])
    moq = pd.to_numeric(orders["moq"], errors="coerce")
    valid = orders[moq.notna()]
    if valid.empty:
        return [KPIResult("moq_compliance_rate", None, "ratio", None, None,
                          start, end, "dataset", {}, PO_SOURCES, True,
                          "formula=compliant/lines with MOQ",
                          "No MOQ terms available in range.")]
    compliant = int((valid["quantity"].astype(float) >= moq[moq.notna()].astype(float)).sum())
    return [KPIResult(
        "moq_compliance_rate", compliant / len(valid), "ratio", float(compliant),
        float(len(valid)), start, end, "dataset", {}, PO_SOURCES, True,
        "formula=qty>=moq over lines", "Observed generated order compliance.")]


def concentration(orders: pd.DataFrame) -> list[KPIResult]:
    """Describe supplier concentration: top share and HHI over spend.

    Descriptive only; Phase 6 builds supplier intelligence on top.
    """
    if orders.empty:
        return []
    start, end = _span(orders["order_date"])
    spend = pd.to_numeric(orders["line_total"], errors="coerce").fillna(0.0)
    total = float(spend.sum())
    if total <= 0:
        return [KPIResult("supplier_hhi", None, "index", None, None, start, end,
                          "dataset", {}, PO_SOURCES, True, "formula=sum(share^2)",
                          "Undefined without positive spend.")]
    by_supplier = orders.assign(_spend=spend).groupby("supplier_id")["_spend"].sum()
    shares = by_supplier / total
    hhi = float((shares ** 2).sum())
    return [
        KPIResult("top_supplier_spend_share", float(shares.max()), "ratio",
                  float(by_supplier.max()), total, start, end, "dataset", {},
                  PO_SOURCES, True, "formula=max(supplier spend)/total",
                  "Largest generated spend share; descriptive only."),
        KPIResult("supplier_hhi", hhi, "index", None, total, start, end,
                  "dataset", {}, PO_SOURCES, True, "formula=sum(share^2)",
                  "Herfindahl index over generated spend; descriptive only."),
    ]
