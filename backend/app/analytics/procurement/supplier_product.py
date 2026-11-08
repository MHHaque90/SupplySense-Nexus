"""Supplier-product relationship analytics (Phase 6).

Joins supplier → supplier_product → product → warehouse → Phase 5
inventory intelligence without losing warehouse-level exposure.
"""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.procurement import lead_times
from backend.app.analytics.procurement.types import (
    ProcurementIntelligenceConfig,
    SupplierProductMetrics,
)


def describe_relationship(
    supplier_id: str,
    supplier_name: str,
    product_id: str,
    product_name: str,
    po_lines: pd.DataFrame,
    shipments: pd.DataFrame,
    moq: float | None,
    analysis_date: date,
    config: ProcurementIntelligenceConfig,
    intelligence: list[InventoryIntelligenceResult] | None = None,
) -> SupplierProductMetrics:
    """Describe one supplier/product relationship with linked exposure."""
    own_lines = po_lines[
        (po_lines["supplier_id"] == supplier_id)
        & (po_lines["product_id"] == product_id)
        & (pd.to_datetime(po_lines["order_date"]).dt.date <= analysis_date)
    ]
    own_shipments = shipments[
        (shipments["supplier_id"] == supplier_id)
        & (shipments["po_id"].astype(str).isin(set(own_lines["po_id"].astype(str))))
        & (shipments["actual_arrival_date"].notna())
        & (pd.to_datetime(shipments["actual_arrival_date"]).dt.date <= analysis_date)
    ]
    delivered = len(own_shipments)
    on_time = None
    if delivered:
        delays = own_shipments["delay_days"].astype(float)
        on_time = float((delays <= config.late_grace_days).sum() / delivered)
    lead = lead_times.describe_relationship_lead_time(
        supplier_id, product_id, po_lines, shipments, None, analysis_date, config
    )
    compliant = None
    if moq is not None and not own_lines.empty:
        compliant = float((own_lines["quantity"].astype(float) >= moq).sum() / len(own_lines))
    metrics = SupplierProductMetrics(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        product_id=product_id,
        product_name=product_name,
        po_count=int(own_lines["po_id"].nunique()),
        ordered_quantity=float(own_lines["quantity"].sum()),
        received_quantity=(
            float(own_lines[own_lines["po_id"].astype(str).isin(
                set(own_shipments["po_id"].astype(str)))]["quantity"].sum())
            if delivered else (0.0 if not own_lines.empty else None)
        ),
        shipment_count=delivered,
        observed_lead_time_days=lead.average_observed_days,
        on_time_rate=on_time,
        moq=moq,
        moq_compliance_rate=compliant,
    )
    for result in intelligence or []:
        if result.product_id != product_id:
            continue
        warehouse = result.warehouse_id
        if warehouse not in metrics.exposed_warehouses:
            metrics.exposed_warehouses.append(warehouse)
        health = result.health.health if result.health else "UNKNOWN"
        if health in ("AT_RISK", "CRITICAL") and warehouse not in metrics.at_risk_warehouses:
            metrics.at_risk_warehouses.append(warehouse)
        if health == "STOCKOUT" and warehouse not in metrics.stockout_warehouses:
            metrics.stockout_warehouses.append(warehouse)
        if result.forecast and result.forecast.confidence.get("level") == "limited validation support":
            metrics.high_uncertainty = True
    return metrics
