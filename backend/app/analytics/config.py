"""Centralized analytics configuration (Phase 3)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AnalyticsConfig:
    """Typed configuration for analytics, validation, and reporting."""

    forecast_horizon: int = 28
    validation_step: int = 28
    min_history: int = 90
    seasonal_periods: tuple[int, ...] = (7, 30)
    moving_average_windows: tuple[int, ...] = (7, 14, 28)
    lag_periods: tuple[int, ...] = (1, 7, 14, 28)
    ses_alpha: float = 0.3
    comparison_metric: str = "mae"
    zero_threshold: float = 1e-9
    dimensions: tuple[str, ...] = ("product_id", "warehouse_id")
    grains: tuple[str, ...] = ("day", "week", "month")
    extra_metrics: tuple[str, ...] = field(default_factory=lambda: ("mae", "rmse", "smape"))

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view of the configuration."""
        return {
            "forecast_horizon": self.forecast_horizon,
            "validation_step": self.validation_step,
            "min_history": self.min_history,
            "seasonal_periods": list(self.seasonal_periods),
            "moving_average_windows": list(self.moving_average_windows),
            "lag_periods": list(self.lag_periods),
            "ses_alpha": self.ses_alpha,
            "comparison_metric": self.comparison_metric,
        }


DEFAULT_ANALYTICS_CONFIG = AnalyticsConfig()
