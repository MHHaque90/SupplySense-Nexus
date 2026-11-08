"""Descriptive supplier performance aggregation (Phase 6).

Point-in-time discipline: only purchase orders placed on or before the
analysis date and shipments actually arrived on or before it are
counted. Received quantity is inferred: a PO line counts as received
when a delivered shipment exists for its purchase order (documented
assumption; per-line partial fulfillment is not represented).
"""

from datetime import date

import pandas as pd

from backend.app.analytics.procurement.types import (
    ProcurementIntelligenceConfig,
    SupplierPerformance,
)


def describe_supplier(
    supplier_id: str,
    supplier_name: str,
    po_lines: pd.DataFrame,
    shipments: pd.DataFrame,
    analysis_date: date,
    config: ProcurementIntelligenceConfig,
) -> SupplierPerformance:
    """Aggregate descriptive performance for one supplier at a date."""
    missing: list[str] = []
    own_lines = po_lines[
        (po_lines["supplier_id"] == supplier_id)
        & (pd.to_datetime(po_lines["order_date"]).dt.date <= analysis_date)
    ]
    own_shipments = shipments[
        (shipments["supplier_id"] == supplier_id)
        & (shipments["actual_arrival_date"].notna())
        & (pd.to_datetime(shipments["actual_arrival_date"]).dt.date <= analysis_date)
    ]
    if own_lines.empty:
        missing.append("purchase_order_history")
    if own_shipments.empty:
        missing.append("delivered_shipments")
    delivered_pos = set(own_shipments["po_id"].astype(str).unique())
    received = float(own_lines[own_lines["po_id"].astype(str).isin(delivered_pos)]["quantity"].sum())
    delays = own_shipments["delay_days"].astype(float).dropna()
    late = delays[delays > config.late_grace_days]
    completed = len(own_shipments)
    order_dates = {
        str(po_id): pd.to_datetime(day).date()
        for po_id, day in own_lines.drop_duplicates("po_id")[["po_id", "order_date"]].itertuples(index=False)
    }
    lead_values = []
    for _, row in own_shipments.iterrows():
        order_date = order_dates.get(str(row["po_id"]))
        arrival = row["actual_arrival_date"]
        if order_date is None or pd.isna(arrival):
            continue
        lead_values.append(float((pd.to_datetime(arrival).date() - order_date).days))
    lead_times = pd.Series(lead_values)
    return SupplierPerformance(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        analysis_date=analysis_date.isoformat(),
        po_count=int(own_lines["po_id"].nunique()),
        po_line_count=len(own_lines),
        ordered_quantity=float(own_lines["quantity"].sum()),
        received_quantity=received if completed else None,
        shipment_count=int(
            ((shipments["supplier_id"] == supplier_id)
             & (pd.to_datetime(shipments["expected_arrival_date"]).dt.date <= analysis_date)).sum()
        ) if not shipments.empty else 0,
        completed_shipments=completed,
        on_time_shipments=int(completed - len(late)),
        late_shipments=int(len(late)),
        on_time_rate=(float(completed - len(late)) / completed) if completed else None,
        average_delay_days=float(delays.mean()) if len(delays) else None,
        median_delay_days=float(delays.median()) if len(delays) else None,
        max_delay_days=float(delays.max()) if len(delays) else None,
        average_lead_time_days=float(lead_times.mean()) if len(lead_times) else None,
        median_lead_time_days=float(lead_times.median()) if len(lead_times) else None,
        min_lead_time_days=float(lead_times.min()) if len(lead_times) else None,
        max_lead_time_days=float(lead_times.max()) if len(lead_times) else None,
        lead_time_std=float(lead_times.std(ddof=0)) if len(lead_times) else None,
        missing_evidence=missing,
    )
