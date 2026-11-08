"""MOQ intelligence, descriptive only (Phase 6).

Reports minimum order quantities, compliance, and order-to-MOQ
ratios. Never EOQ, never optimal quantities, never batch-size advice.
"""

import pandas as pd

from backend.app.analytics.procurement.types import MOQMetrics


def describe_moq(
    supplier_id: str,
    product_id: str | None,
    po_lines: pd.DataFrame,
    moq: float | None,
) -> MOQMetrics:
    """Describe MOQ behavior for a supplier, optionally per product."""
    own = po_lines[po_lines["supplier_id"] == supplier_id]
    if product_id is not None:
        own = own[own["product_id"] == product_id]
    metrics = MOQMetrics(supplier_id=supplier_id, product_id=product_id, moq=moq)
    if own.empty or moq is None or moq <= 0:
        return metrics
    quantities = own["quantity"].astype(float)
    compliant = int((quantities >= moq).sum())
    metrics.orders = len(own)
    metrics.compliant_orders = compliant
    metrics.compliance_rate = compliant / len(own)
    metrics.below_moq_orders = len(own) - compliant
    ratios = quantities / moq
    metrics.min_order_ratio = float(ratios.min())
    metrics.median_order_ratio = float(ratios.median())
    return metrics
