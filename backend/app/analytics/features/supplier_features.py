"""Supplier descriptive features (Phase 3, descriptive only).

No scoring or ranking: these frames describe lead times, delays, and
order volumes so Phase 6 can build supplier intelligence on top.
"""

import pandas as pd


def supplier_lead_time_frame(supplier_links: pd.DataFrame) -> pd.DataFrame:
    """Summarize contracted lead times and MOQs per supplier."""
    if supplier_links.empty:
        return pd.DataFrame(columns=["supplier_id", "products_linked", "avg_lead_time_days",
                                     "min_moq", "supplier_name", "country"])
    grouped = supplier_links.groupby(["supplier_id", "supplier_name", "country"], as_index=False).agg(
        products_linked=("product_id", "nunique"),
        avg_lead_time_days=("lead_time_days", "mean"),
        min_moq=("min_order_qty", "min"),
    )
    return grouped.sort_values("supplier_id").reset_index(drop=True)


def supplier_shipment_frame(shipments: pd.DataFrame) -> pd.DataFrame:
    """Summarize observed shipment delays per supplier (delivered only)."""
    if shipments.empty:
        return pd.DataFrame(columns=["supplier_id", "shipments", "avg_delay_days",
                                     "late_shipments", "late_rate"])
    delivered = shipments[shipments["actual_arrival_date"].notna()].copy()
    if delivered.empty:
        return pd.DataFrame(columns=["supplier_id", "shipments", "avg_delay_days",
                                     "late_shipments", "late_rate"])
    grouped = delivered.groupby("supplier_id", as_index=False).agg(
        shipments=("shipment_id", "count"),
        avg_delay_days=("delay_days", "mean"),
        late_shipments=("delay_days", lambda s: (s > 0).sum()),
    )
    grouped["late_rate"] = grouped["late_shipments"] / grouped["shipments"]
    return grouped.sort_values("supplier_id").reset_index(drop=True)
