"""Open purchase order intelligence (Phase 6, descriptive only).

Open = status ordered or partially_received at the analysis date (the
schema's outstanding states). Received quantity is inferred from
delivered shipments linked to the PO (documented assumption); remaining
is ordered minus received, floored at zero. Nothing here plans or
optimizes procurement.
"""

from datetime import date

import pandas as pd

from backend.app.analytics.procurement.types import OpenOrderMetrics

OPEN_STATUSES = ("ordered", "partially_received")


def describe_open_orders(
    po_lines: pd.DataFrame,
    shipments: pd.DataFrame,
    analysis_date: date,
    supplier_ids: list[str] | None = None,
) -> list[OpenOrderMetrics]:
    """Describe outstanding PO lines with overdue and arrival status."""
    lines = po_lines[pd.to_datetime(po_lines["order_date"]).dt.date <= analysis_date]
    if supplier_ids:
        lines = lines[lines["supplier_id"].isin(supplier_ids)]
    lines = lines[lines["status"].isin(OPEN_STATUSES)]
    if lines.empty:
        return []
    delivered_pos = set(shipments[
        (shipments["actual_arrival_date"].notna())
        & (pd.to_datetime(shipments["actual_arrival_date"]).dt.date <= analysis_date)
    ]["po_id"].astype(str).unique())
    expected_by_po = (
        shipments.dropna(subset=["expected_arrival_date"])
        .groupby("po_id")["expected_arrival_date"]
        .min()
    )
    results: list[OpenOrderMetrics] = []
    for _, row in lines.iterrows():
        po_id = str(row["po_id"])
        ordered = float(row["quantity"])
        received = ordered if po_id in delivered_pos else 0.0
        remaining = max(0.0, ordered - received)
        expected = row["expected_delivery_date"]
        expected_str = str(pd.to_datetime(expected).date()) if pd.notna(expected) else None
        if po_id in expected_by_po.index:
            expected_str = str(pd.to_datetime(expected_by_po.loc[po_id]).date())
        overdue = bool(expected_str and expected_str < analysis_date.isoformat() and remaining > 0)
        if remaining <= 0:
            arrival_status = "received"
        elif overdue:
            arrival_status = "overdue"
        elif expected_str:
            arrival_status = "expected"
        else:
            arrival_status = "unknown"
        order_day = pd.to_datetime(row["order_date"]).date()
        results.append(OpenOrderMetrics(
            po_id=po_id,
            po_number=str(row["po_number"]) if "po_number" in row else po_id,
            supplier_id=str(row["supplier_id"]),
            product_id=str(row["product_id"]),
            order_date=str(order_day),
            expected_arrival=expected_str,
            ordered_quantity=ordered,
            received_quantity=received,
            remaining_quantity=remaining,
            overdue=overdue,
            days_outstanding=(analysis_date - order_day).days,
            arrival_status=arrival_status,
        ))
    return results
