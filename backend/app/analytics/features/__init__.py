"""Feature engineering for SupplySense Nexus analytics (Phase 3).

LEAKAGE RULE: every historical feature is computed from values at or
before the prediction cutoff. Rolling statistics always operate on a
shifted series; lags never include the current target. Tests assert
that perturbing future values cannot change past features.
"""

from backend.app.analytics.features import (
    calendar_features,
    demand_features,
    inventory_features,
    profiles,
    supplier_features,
)

__all__ = [
    "calendar_features",
    "demand_features",
    "inventory_features",
    "profiles",
    "supplier_features",
]
