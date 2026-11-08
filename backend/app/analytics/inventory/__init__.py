"""Inventory intelligence for SupplySense Nexus (Phase 5).

Descriptive, auditable signals over inventory positions, Phase 4
forecasts, and service evidence. No optimization: reorder outputs are
SIGNALS ("does this position require attention?"), never optimized
order quantities, supplier allocations, or safety-stock levels.

This dataset is synthetic and is generated solely for demonstration,
testing, analytics development, and portfolio purposes.
"""

from backend.app.analytics.inventory import (
    aging,
    anomalies,
    concentration,
    coverage,
    forecast_inputs,
    health,
    position,
    projection,
    reorder_signals,
    reports,
    service,
    stockout,
    turnover,
    types,
    uncertainty,
)

__all__ = [
    "aging",
    "anomalies",
    "concentration",
    "coverage",
    "forecast_inputs",
    "health",
    "position",
    "projection",
    "reorder_signals",
    "reports",
    "service",
    "stockout",
    "turnover",
    "types",
    "uncertainty",
]
