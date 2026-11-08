"""Structured forecasting results (Phase 3 results, Phase 4 contracts)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ForecastResult:
    """One model forecast over a horizon."""

    model_name: str
    series_id: str
    cutoff: str
    horizon: int
    predictions: list[float]
    history_length: int
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the forecast."""
        return {
            "model_name": self.model_name,
            "series_id": self.series_id,
            "cutoff": self.cutoff,
            "horizon": self.horizon,
            "predictions": self.predictions,
            "history_length": self.history_length,
            "parameters": self.parameters,
        }


@dataclass
class ValidationFold:
    """One walk-forward fold with metrics."""

    model_name: str
    series_id: str
    cutoff: str
    horizon: int
    actuals: list[float]
    predictions: list[float]
    metrics: dict[str, float | None]
    train_length: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the fold."""
        return {
            "model_name": self.model_name,
            "series_id": self.series_id,
            "cutoff": self.cutoff,
            "horizon": self.horizon,
            "actuals": self.actuals,
            "predictions": self.predictions,
            "metrics": self.metrics,
            "train_length": self.train_length,
        }


@dataclass
class SelectionResult:
    """Structured outcome of per-series model selection (Phase 4)."""

    series_id: str
    product_id: str
    warehouse_id: str
    selected_model: str
    fallback_used: bool
    validation_metric: str
    validation_score: float | None
    validation_folds: int
    demand_profile: str
    candidates: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)
    explanation: str = ""
    confidence: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    training_start: str = ""
    training_end: str = ""
    model_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the selection."""
        return {
            "series_id": self.series_id,
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "selected_model": self.selected_model,
            "fallback_used": self.fallback_used,
            "validation_metric": self.validation_metric,
            "validation_score": self.validation_score,
            "validation_folds": self.validation_folds,
            "demand_profile": self.demand_profile,
            "candidates": self.candidates,
            "skipped": self.skipped,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "training_start": self.training_start,
            "training_end": self.training_end,
            "model_config": self.model_config,
        }


@dataclass
class ForecastOutput:
    """Structured forecast with intervals and provenance (Phase 4).

    Point forecasts are floored at zero because demand is
    non-negative; raw backtest predictions stay unclamped so metrics
    remain honest.
    """

    series_id: str
    product_id: str
    warehouse_id: str
    origin: str
    forecast_dates: list[str] = field(default_factory=list)
    horizon: int = 0
    model_name: str = ""
    point: list[float] = field(default_factory=list)
    lower: list[float] = field(default_factory=list)
    upper: list[float] = field(default_factory=list)
    confidence_level: float = 0.95
    interval_method: str = "empirical_residual_quantile"
    demand_profile: str = ""
    validation_metric: str = ""
    validation_score: float | None = None
    validation_folds: int = 0
    training_start: str = ""
    training_end: str = ""
    model_config: dict[str, Any] = field(default_factory=dict)
    synthetic: bool = True
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    explanation: str = ""
    confidence: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the forecast."""
        return {
            "series_id": self.series_id,
            "product_id": self.product_id,
            "warehouse_id": self.warehouse_id,
            "origin": self.origin,
            "forecast_dates": self.forecast_dates,
            "horizon": self.horizon,
            "model_name": self.model_name,
            "point": self.point,
            "lower": self.lower,
            "upper": self.upper,
            "confidence_level": self.confidence_level,
            "interval_method": self.interval_method,
            "demand_profile": self.demand_profile,
            "validation_metric": self.validation_metric,
            "validation_score": self.validation_score,
            "validation_folds": self.validation_folds,
            "training_start": self.training_start,
            "training_end": self.training_end,
            "model_config": self.model_config,
            "synthetic": self.synthetic,
            "assumptions": self.assumptions,
            "warnings": self.warnings,
            "explanation": self.explanation,
            "confidence": self.confidence,
        }
