"""Synthetic ERP data foundation for SupplySense Nexus (Phase 2).

This dataset is synthetic and is generated solely for demonstration,
testing, analytics development, and portfolio purposes. It does not
represent any real company, supplier, product, or market behavior.

All generated operational records carry ``data_source_label = "synthetic"``.
Disruption records carry ``data_source_label = "simulated"``.
"""

GENERATOR_VERSION = "2.0.0"

SYNTHETIC_DISCLAIMER = (
    "This dataset is synthetic and is generated solely for demonstration, "
    "testing, analytics development, and portfolio purposes."
)

__all__ = ["GENERATOR_VERSION", "SYNTHETIC_DISCLAIMER"]
