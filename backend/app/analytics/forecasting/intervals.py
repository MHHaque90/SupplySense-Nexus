"""Prediction intervals from empirical residual quantiles (Phase 4).

Methodology: pool walk-forward residuals (actual − predicted) for the
selected model and take empirical quantiles at (1−level)/2 and
1−(1−level)/2. Intervals are NOT guarantees; they describe in-sample
backtest dispersion. Empirical coverage on synthetic data does not
imply future real-world coverage. Lower bounds are floored at zero
because demand is non-negative.
"""

from dataclasses import dataclass

import numpy as np

from backend.app.analytics.forecasting.result import ValidationFold

SUPPORTED_LEVELS = (0.8, 0.95)


@dataclass(frozen=True)
class IntervalResult:
    """Prediction interval for one forecast."""

    level: float
    lower: list[float]
    upper: list[float]
    method: str = "empirical_residual_quantile"
    in_sample_coverage: float | None = None
    mean_width: float | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view of the interval."""
        return {
            "level": self.level,
            "lower": self.lower,
            "upper": self.upper,
            "method": self.method,
            "in_sample_coverage": self.in_sample_coverage,
            "mean_width": self.mean_width,
        }


def residual_quantiles(residuals: list[float], level: float) -> tuple[float, float]:
    """Return the lower/upper empirical residual quantiles for a level."""
    if level not in SUPPORTED_LEVELS:
        raise ValueError(f"Unsupported level {level}; use one of {SUPPORTED_LEVELS}.")
    if not residuals:
        raise ValueError("No residuals available for interval construction.")
    data = np.asarray(residuals, dtype=float)
    alpha = 1.0 - level
    return float(np.quantile(data, alpha / 2.0)), float(np.quantile(data, 1.0 - alpha / 2.0))


def build_intervals(
    predictions: list[float],
    residuals: list[float],
    level: float = 0.95,
    actuals: list[float] | None = None,
) -> IntervalResult:
    """Build intervals around point forecasts from backtest residuals."""
    lower_q, upper_q = residual_quantiles(residuals, level)
    lower = [max(0.0, float(p) + lower_q) for p in predictions]
    upper = [max(0.0, float(p) + upper_q) for p in predictions]
    coverage: float | None = None
    if actuals is not None and len(actuals) == len(predictions):
        hits = sum(1 for a, lo, hi in zip(actuals, lower, upper) if lo <= a <= hi)
        coverage = hits / len(actuals) if actuals else None
    widths = [hi - lo for hi, lo in zip(upper, lower)]
    return IntervalResult(
        level=level,
        lower=lower,
        upper=upper,
        in_sample_coverage=coverage,
        mean_width=float(np.mean(widths)) if widths else None,
    )


def collect_residuals(folds: list[ValidationFold], model_name: str) -> list[float]:
    """Pool actual-minus-predicted residuals for one model across folds."""
    residuals: list[float] = []
    for fold in folds:
        if fold.model_name != model_name:
            continue
        residuals.extend(float(a) - float(p) for a, p in zip(fold.actuals, fold.predictions))
    return residuals


def interval_score(
    actuals: list[float], lower: list[float], upper: list[float], level: float = 0.95
) -> float:
    """Winkler interval score (lower is better); penalizes misses by width-normalized excess."""
    if not (len(actuals) == len(lower) == len(upper)) or not actuals:
        raise ValueError("Interval score needs non-empty aligned inputs.")
    alpha = 1.0 - level
    total = 0.0
    for actual, low, high in zip(actuals, lower, upper):
        total += (high - low) + (2.0 / alpha) * (low - actual) * (actual < low)
        total += (2.0 / alpha) * (actual - high) * (actual > high)
    return float(total / len(actuals))
