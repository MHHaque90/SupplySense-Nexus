"""Supplier-linked inventory exposure (Phase 6).

Answers "how much inventory exposure is connected to this supplier
relationship" by joining supplier → supplier_product → product →
warehouse → Phase 5 intelligence. Never "which supplier to choose".
"""

from backend.app.analytics.inventory.reports import InventoryIntelligenceResult
from backend.app.analytics.procurement.types import OpenOrderMetrics, SupplierExposure


def describe_supplier_exposure(
    supplier_id: str,
    supplier_name: str,
    product_ids: list[str],
    intelligence: list[InventoryIntelligenceResult],
    open_orders: list[OpenOrderMetrics],
    inbound_by_po_product: dict[tuple[str, str], float] | None = None,
) -> SupplierExposure:
    """Aggregate Phase 5 exposure signals for one supplier's products."""
    exposure = SupplierExposure(supplier_id=supplier_id, supplier_name=supplier_name)
    owned = set(product_ids)
    for result in intelligence:
        if result.product_id not in owned:
            continue
        if result.warehouse_id not in exposure.affected_warehouses:
            exposure.affected_warehouses.append(result.warehouse_id)
        if result.product_id not in exposure.affected_products:
            exposure.affected_products.append(result.product_id)
        health = result.health.health if result.health else "UNKNOWN"
        if health in ("AT_RISK", "CRITICAL") and result.product_id not in exposure.at_risk_products:
            exposure.at_risk_products.append(result.product_id)
        if health == "STOCKOUT" and result.product_id not in exposure.stockout_products:
            exposure.stockout_products.append(result.product_id)
        if result.reorder and result.reorder.urgency == "urgent":
            if result.product_id not in exposure.urgent_products:
                exposure.urgent_products.append(result.product_id)
        if result.forecast and result.forecast.confidence.get("level") == "limited validation support":
            if result.product_id not in exposure.high_uncertainty_products:
                exposure.high_uncertainty_products.append(result.product_id)
    for order in open_orders:
        if order.supplier_id != supplier_id:
            continue
        exposure.open_po_quantity += order.remaining_quantity
        if inbound_by_po_product is not None:
            exposure.inbound_quantity += inbound_by_po_product.get(
                (order.po_id, order.product_id), 0.0
            )
    return exposure
