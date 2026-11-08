"""Data source labels for SupplySense Nexus.

All data must carry one of these labels to distinguish its origin
and prevent synthetic or simulated data from being confused with
real operational data.
"""

from enum import StrEnum


class DataSourceLabel(StrEnum):
    """Enumerates all valid data source labels."""

    PUBLIC = "public"
    SYNTHETIC = "synthetic"
    USER_PROVIDED = "user-provided"
    DERIVED = "derived"
    SIMULATED = "simulated"
    FORECAST = "forecast"
    ESTIMATED = "estimated"
    ILLUSTRATIVE = "illustrative"
    REAL = "real"

    @classmethod
    def values(cls) -> list[str]:
        """Return all valid label values."""
        return [member.value for member in cls]
