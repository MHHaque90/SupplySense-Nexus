"""Model Registry foundation for metadata tracking and version management.

Maintains traceable model version records, reference distributions, and drift evaluation
histories without external services. Compatible with both in-memory usage and
persisted SQLAlchemy ModelVersion rows.
"""

from datetime import UTC, datetime
from typing import Any

from backend.app.analytics.drift.types import (
    DriftEvaluationResult,
    ModelMetadata,
    ModelStatus,
)
from backend.app.core.data_labels import DataSourceLabel

# Known Phase 4 forecasting model definitions
DEFAULT_FORECAST_MODELS: tuple[tuple[str, str], ...] = (
    ("zero", "baseline"),
    ("naive", "baseline"),
    ("seasonal_naive", "baseline"),
    ("moving_average", "baseline"),
    ("drift", "baseline"),
    ("ses", "baseline"),
    ("holt", "statistical"),
    ("holt_winters", "statistical"),
    ("autoreg", "statistical"),
    ("croston", "intermittent"),
    ("hgb", "ml"),
)

DEFAULT_VERSION: str = "4.0.0"


class ModelRegistry:
    """Registry maintaining traceable metadata and version records for models."""

    def __init__(self, auto_seed: bool = True) -> None:
        """Initialize registry with optional seed of existing forecasting models."""
        self._models: dict[str, ModelMetadata] = {}  # key: model_id
        self._name_version_index: dict[tuple[str, str], str] = {}  # key: (model_name, version) -> model_id
        self._active_versions: dict[str, str] = {}  # key: model_name -> model_id
        self._drift_history: list[DriftEvaluationResult] = []

        if auto_seed:
            self._seed_default_models()

    def _seed_default_models(self) -> None:
        """Seed existing Phase 4 models as active version 4.0.0."""
        for name, m_type in DEFAULT_FORECAST_MODELS:
            model_id = f"{name}:{DEFAULT_VERSION}"
            entry = ModelMetadata(
                model_id=model_id,
                model_name=name,
                version=DEFAULT_VERSION,
                model_type=m_type,
                status=ModelStatus.ACTIVE,
                features=["history"],
                data_source_label=DataSourceLabel.DERIVED.value,
            )
            self._models[model_id] = entry
            self._name_version_index[(name, DEFAULT_VERSION)] = model_id
            self._active_versions[name] = model_id

    def register_model(self, metadata: ModelMetadata) -> ModelMetadata:
        """Register or update a model metadata entry."""
        model_id = metadata.model_id
        self._models[model_id] = metadata
        self._name_version_index[(metadata.model_name, metadata.version)] = model_id

        if metadata.status == ModelStatus.ACTIVE:
            self._active_versions[metadata.model_name] = model_id

        return metadata

    def create_version(
        self,
        model_name: str,
        version: str,
        model_type: str,
        status: ModelStatus = ModelStatus.CANDIDATE,
        training_window_start: str | None = None,
        training_window_end: str | None = None,
        features: list[str] | None = None,
        hyperparameters: dict[str, Any] | None = None,
        metrics: dict[str, float] | None = None,
        reference_distribution: list[float] | None = None,
        data_source_label: str = DataSourceLabel.DERIVED.value,
    ) -> ModelMetadata:
        """Create and register a new version for a model."""
        model_id = f"{model_name}:{version}"
        now_iso = datetime.now(UTC).isoformat()
        metadata = ModelMetadata(
            model_id=model_id,
            model_name=model_name,
            version=version,
            model_type=model_type,
            status=status,
            training_window_start=training_window_start,
            training_window_end=training_window_end,
            features=list(features or []),
            hyperparameters=dict(hyperparameters or {}),
            metrics=dict(metrics or {}),
            reference_distribution=list(reference_distribution or []),
            created_at=now_iso,
            updated_at=now_iso,
            data_source_label=data_source_label,
        )
        return self.register_model(metadata)

    def get_model(self, model_id: str) -> ModelMetadata | None:
        """Fetch model metadata by unique model identifier."""
        return self._models.get(model_id)

    def get_version(self, model_name: str, version: str) -> ModelMetadata | None:
        """Fetch model metadata by name and version."""
        model_id = self._name_version_index.get((model_name, version))
        if model_id:
            return self._models.get(model_id)
        return None

    def get_active_version(self, model_name: str) -> ModelMetadata | None:
        """Fetch the currently active model version for a given model name."""
        model_id = self._active_versions.get(model_name)
        if model_id:
            return self._models.get(model_id)
        return None

    def list_models(
        self,
        model_name: str | None = None,
        status: ModelStatus | None = None,
    ) -> list[ModelMetadata]:
        """List registered models with optional filtering by name or status."""
        results = list(self._models.values())
        if model_name:
            results = [m for m in results if m.model_name == model_name]
        if status:
            results = [m for m in results if m.status == status]
        return results

    def set_active_version(self, model_name: str, version: str) -> ModelMetadata:
        """Set a specific version as the active version for a model name."""
        target = self.get_version(model_name, version)
        if not target:
            raise ValueError(f"Model version '{model_name}:{version}' is not registered.")

        # Update previous active to ARCHIVED if different
        current_active_id = self._active_versions.get(model_name)
        if current_active_id and current_active_id != target.model_id:
            old_meta = self._models[current_active_id]
            updated_old = ModelMetadata(
                model_id=old_meta.model_id,
                model_name=old_meta.model_name,
                version=old_meta.version,
                model_type=old_meta.model_type,
                status=ModelStatus.ARCHIVED,
                training_window_start=old_meta.training_window_start,
                training_window_end=old_meta.training_window_end,
                features=old_meta.features,
                hyperparameters=old_meta.hyperparameters,
                metrics=old_meta.metrics,
                reference_distribution=old_meta.reference_distribution,
                created_at=old_meta.created_at,
                updated_at=datetime.now(UTC).isoformat(),
                data_source_label=old_meta.data_source_label,
            )
            self._models[old_meta.model_id] = updated_old

        # Promote target to ACTIVE
        now_iso = datetime.now(UTC).isoformat()
        updated_target = ModelMetadata(
            model_id=target.model_id,
            model_name=target.model_name,
            version=target.version,
            model_type=target.model_type,
            status=ModelStatus.ACTIVE,
            training_window_start=target.training_window_start,
            training_window_end=target.training_window_end,
            features=target.features,
            hyperparameters=target.hyperparameters,
            metrics=target.metrics,
            reference_distribution=target.reference_distribution,
            created_at=target.created_at,
            updated_at=now_iso,
            data_source_label=target.data_source_label,
        )
        self._models[target.model_id] = updated_target
        self._active_versions[model_name] = target.model_id
        return updated_target

    def record_drift(self, result: DriftEvaluationResult) -> None:
        """Record an auditable drift evaluation result."""
        self._drift_history.append(result)

    def get_drift_history(
        self,
        model_id: str | None = None,
        limit: int = 50,
    ) -> list[DriftEvaluationResult]:
        """Fetch chronological drift evaluation history."""
        records = self._drift_history
        if model_id:
            records = [r for r in records if r.model_id == model_id]
        return records[-limit:]
