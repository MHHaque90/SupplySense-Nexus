"""Analytics foundation for SupplySense Nexus (Phase 3).

Deterministic, leakage-safe analytics over the Phase 1 PostgreSQL schema
and the Phase 2 synthetic dataset. Pure functions operate on pandas
frames; database access lives in ``datasets`` loaders only.

This dataset is synthetic and is generated solely for demonstration,
testing, analytics development, and portfolio purposes. Every report
derived from it must carry the synthetic-data disclaimer.
"""

SYNTHETIC_ANALYTICS_DISCLAIMER = (
    "SYNTHETIC DATA — the synthetic dataset shows illustrative patterns only. "
    "The observed generated records indicate model behavior under this "
    "simulation configuration; they are not real business performance."
)

__all__ = ["SYNTHETIC_ANALYTICS_DISCLAIMER"]
