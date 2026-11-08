"""Typed analytics contracts (Phase 3)."""

from dataclasses import dataclass, field
from typing import Any


class InsufficientHistoryError(ValueError):
    """Raised when a series is too short for the requested operation."""


class UnsupportedModelError(ValueError):
    """Raised when a model cannot produce a forecast for a series."""


@dataclass(frozen=True)
class KPIResult:
    """Auditable key performance indicator."""

    metric_name: str
    value: float | None
    unit: str
    numerator: float | None
    denominator: float | None
    time_start: str
    time_end: str
    grain: str
    dimensions: dict[str, str]
    source_tables: list[str]
    synthetic: bool = True
    formula: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the KPI."""
        return {
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "time_start": self.time_start,
            "time_end": self.time_end,
            "grain": self.grain,
            "dimensions": self.dimensions,
            "source_tables": self.source_tables,
            "synthetic": self.synthetic,
            "formula": self.formula,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class SeriesProfile:
    """Analytical demand profile for one series."""

    series_id: str
    profile: str
    mean_demand: float
    std_demand: float
    coefficient_of_variation: float | None
    zero_ratio: float
    nonzero_count: int
    mean_interval_nonzero: float | None
    trend_slope_per_day: float
    observations: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the profile."""
        return {
            "series_id": self.series_id,
            "profile": self.profile,
            "mean_demand": self.mean_demand,
            "std_demand": self.std_demand,
            "coefficient_of_variation": self.coefficient_of_variation,
            "zero_ratio": self.zero_ratio,
            "nonzero_count": self.nonzero_count,
            "mean_interval_nonzero": self.mean_interval_nonzero,
            "trend_slope_per_day": self.trend_slope_per_day,
            "observations": self.observations,
        }


@dataclass
class ModelComparison:
    """Per-series model comparison outcome."""

    series_id: str
    metric: str
    scores: dict[str, float] = field(default_factory=dict)
    skipped: dict[str, str] = field(default_factory=dict)
    selected_model: str | None = None
    note: str = (
        "Lowest observed validation error for this series under this "
        "metric/configuration; not a global best-model claim."
    )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the comparison."""
        return {
            "series_id": self.series_id,
            "metric": self.metric,
            "scores": self.scores,
            "skipped": self.skipped,
            "selected_model": self.selected_model,
            "note": self.note,
        }
