"""Projected inventory trajectories (Phase 5).

Demand-only depletion plus KNOWN inbound: shipments that are not yet
delivered (null actual arrival) and expected inside the window,
allocated by purchase-order line quantity. Each open PO/product
contributes once, at its earliest expected arrival in the window;
split-shipment partial quantities are not represented (documented).
No future purchase orders are created and no procurement is simulated.
Without known inbound the trajectory is demand-only (documented).
"""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory.types import ForecastInput, ProjectedInventoryPoint


def known_inbound(
    product_id: str,
    shipments: pd.DataFrame,
    po_lines: pd.DataFrame,
    analysis_date: date,
    horizon_end: date,
) -> dict[str, float]:
    """Map forecast dates to known inbound quantities for one product.

    Only shipments with no actual arrival and an expected date in
    (analysis_date, horizon_end] contribute.
    """
    inbound: dict[str, float] = {}
    if shipments.empty or po_lines.empty:
        return inbound
    pending = shipments[
        (shipments["actual_arrival_date"].isna())
        & (pd.to_datetime(shipments["expected_arrival_date"]).dt.date > analysis_date)
        & (pd.to_datetime(shipments["expected_arrival_date"]).dt.date <= horizon_end)
    ]
    if pending.empty:
        return inbound
    lines = po_lines[po_lines["product_id"] == product_id]
    if lines.empty:
        return inbound
    line_qty = lines.groupby("po_id")["quantity"].sum()
    earliest: dict[str, tuple[str, float]] = {}
    for _, row in pending.iterrows():
        po_id = str(row["po_id"])
        if po_id not in line_qty.index:
            continue
        arrival = str(pd.to_datetime(row["expected_arrival_date"]).date())
        quantity = float(line_qty.loc[po_id])
        if po_id not in earliest or arrival < earliest[po_id][0]:
            earliest[po_id] = (arrival, quantity)
    for arrival, quantity in earliest.values():
        inbound[arrival] = inbound.get(arrival, 0.0) + quantity
    return inbound


def project_trajectory(
    on_hand: float,
    forecast: ForecastInput,
    inbound: dict[str, float] | None = None,
) -> list[ProjectedInventoryPoint]:
    """Project daily inventory over the forecast horizon."""
    inbound = inbound or {}
    trajectory: list[ProjectedInventoryPoint] = []
    balance = on_hand
    for position in range(forecast.horizon):
        forecast_date = forecast.forecast_dates[position]
        demand = forecast.point[position]
        arriving = inbound.get(forecast_date, 0.0)
        balance = balance - demand + arriving
        trajectory.append(ProjectedInventoryPoint(
            date=forecast_date,
            beginning_inventory=balance + demand - arriving,
            forecast_demand=demand,
            lower_demand=forecast.lower[position],
            upper_demand=forecast.upper[position],
            known_inbound=arriving,
            projected_ending=balance,
            projected_stockout=balance <= 0,
        ))
    return trajectory
