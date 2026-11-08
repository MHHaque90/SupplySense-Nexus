"""Data types and contracts for model drift monitoring and model registry."""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from backend.app.core.data_labels import DataSourceLabel


class DriftStatus(StrEnum):
    """Machine-readable drift evaluation states."""

    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NO_DRIFT = "NO_DRIFT"
    DRIFT_DETECTED = "DRIFT_DETECTED"


class ModelStatus(StrEnum):
    """Lifecycle status for registered models."""

    ACTIVE = "active"
    CANDIDATE = "candidate"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


@dataclass(frozen=True)
class ModelMetadata:
    """Immutable model registry metadata entry for version tracking and traceability."""

    model_id: str
    model_name: str
    version: str
    model_type: str
    status: ModelStatus = ModelStatus.CANDIDATE
    training_window_start: str | None = None
    training_window_end: str | None = None
    features: list[str] = field(default_factory=list)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    reference_distribution: list[float] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    data_source_label: str = DataSourceLabel.DERIVED.value

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass(frozen=True)
class DriftEvaluationResult:
    """Auditable result of a deterministic drift evaluation."""

    model_id: str
    model_version: str
    metric: str
    metric_value: float | None
    threshold: float
    status: DriftStatus
    reference_count: int
    current_count: int
    context: dict[str, Any] = field(default_factory=dict)
    p_value: float | None = None
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    data_source_label: str = DataSourceLabel.DERIVED.value

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        data = asdict(self)
        data["status"] = self.status.value
        return data
