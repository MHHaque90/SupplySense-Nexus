"""Supplier & procurement intelligence for SupplySense Nexus (Phase 6).

Descriptive intelligence only. This layer describes supplier
performance, delivery reliability, lead-time behavior, open
procurement exposure, concentration, and supplier-linked inventory
exposure. It never ranks suppliers, never recommends suppliers or
quantities, and never optimizes procurement.

This dataset is synthetic and is generated solely for demonstration,
testing, analytics development, and portfolio purposes. Nothing here
is evidence about real suppliers or real procurement performance.
"""

from backend.app.analytics.procurement import (
    concentration,
    delivery,
    exposure,
    inbound,
    lead_times,
    moq,
    open_orders,
    reports,
    risk_signals,
    service_impact,
    supplier_performance,
    supplier_product,
    types,
)

__all__ = [
    "concentration",
    "delivery",
    "exposure",
    "inbound",
    "lead_times",
    "moq",
    "open_orders",
    "reports",
    "risk_signals",
    "service_impact",
    "supplier_performance",
    "supplier_product",
    "types",
]
