"""Lead-time intelligence: observed vs contracted (Phase 6).

Observed lead time = actual arrival − PO order date, from delivered
shipments only. This describes history; it is not a lead-time forecast
and no lead-time prediction model is implemented here.
"""

from datetime import date, timedelta

import pandas as pd

from backend.app.analytics.procurement.types import (
    LeadTimeMetrics,
    ProcurementIntelligenceConfig,
)


def describe_relationship_lead_time(
    supplier_id: str,
    product_id: str,
    po_lines: pd.DataFrame,
    shipments: pd.DataFrame,
    contracted_days: float | None,
    analysis_date: date,
    config: ProcurementIntelligenceConfig,
) -> LeadTimeMetrics:
    """Describe observed lead times for one supplier/product pair."""
    own_lines = po_lines[
        (po_lines["supplier_id"] == supplier_id)
        & (po_lines["product_id"] == product_id)
        & (pd.to_datetime(po_lines["order_date"]).dt.date <= analysis_date)
    ]
    delivered = shipments[
        (shipments["supplier_id"] == supplier_id)
        & (shipments["actual_arrival_date"].notna())
        & (pd.to_datetime(shipments["actual_arrival_date"]).dt.date <= analysis_date)
    ]
    order_dates = own_lines.drop_duplicates("po_id").set_index("po_id")["order_date"]
    observed: list[float] = []
    delayed = 0
    for _, row in delivered.iterrows():
        po_id = str(row["po_id"])
        if po_id not in order_dates.index:
            continue
        order_date = pd.to_datetime(order_dates.loc[po_id]).date()
        arrival = pd.to_datetime(row["actual_arrival_date"]).date()
        expected = pd.to_datetime(row["expected_arrival_date"]).date()
        observed.append(float((arrival - order_date).days))
        if arrival > expected + timedelta(days=config.late_grace_days):
            delayed += 1
    metrics = LeadTimeMetrics(
        supplier_id=supplier_id,
        product_id=product_id,
        observations=len(observed),
        contracted_days=contracted_days,
    )
    if not observed:
        return metrics
    series = pd.Series(observed)
    metrics.average_observed_days = float(series.mean())
    metrics.median_observed_days = float(series.median())
    metrics.min_observed_days = float(series.min())
    metrics.max_observed_days = float(series.max())
    metrics.std_observed_days = float(series.std(ddof=0)) if len(series) > 1 else 0.0
    metrics.delay_frequency = delayed / len(observed)
    if len(series) >= config.min_lead_time_obs:
        metrics.percentiles = {
            "p25": float(series.quantile(0.25)),
            "p50": float(series.quantile(0.5)),
            "p75": float(series.quantile(0.75)),
            "p90": float(series.quantile(0.9)),
        }
    return metrics
