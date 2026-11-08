"""Baseline forecasting models with a consistent interface (Phase 3).

Every model exposes ``fit(history)`` and ``predict(horizon)``. Models
validate history length up front and raise
:class:`InsufficientHistoryError` instead of producing invalid output.
"""

import numpy as np

from backend.app.analytics.forecasting.result import ForecastResult
from backend.app.analytics.types import InsufficientHistoryError


def _as_array(history: list[float] | np.ndarray | object) -> np.ndarray:
    values = np.asarray(history, dtype=float).ravel()
    if values.size == 0:
        raise InsufficientHistoryError("Empty history: cannot fit any baseline.")
    if not np.all(np.isfinite(values)):
        raise ValueError("History contains non-finite values.")
    return values


class Naive:
    """Repeat the last observation."""

    name = "naive"

    def __init__(self) -> None:
        self._level = 0.0
        self._length = 0

    def fit(self, history: list[float] | np.ndarray) -> "Naive":
        """Fit on history (stores the last observation)."""
        values = _as_array(history)
        self._level = float(values[-1])
        self._length = len(values)
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Forecast a flat line at the last observation."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        return ForecastResult(self.name, "", "", horizon,
                              [self._level] * horizon, self._length)


class SeasonalNaive:
    """Repeat the last seasonal cycle (e.g. 7 for weekly daily data)."""

    name = "seasonal_naive"

    def __init__(self, season: int = 7) -> None:
        if season < 2:
            raise ValueError("Season must be at least 2.")
        self.season = season
        self._cycle: list[float] = []

    def fit(self, history: list[float] | np.ndarray) -> "SeasonalNaive":
        """Fit on history (stores the last full seasonal cycle)."""
        values = _as_array(history)
        if len(values) < self.season:
            raise InsufficientHistoryError(
                f"Seasonal naive (season={self.season}) needs at least "
                f"{self.season} observations, got {len(values)}."
            )
        self._cycle = [float(v) for v in values[-self.season:]]
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Tile the stored seasonal cycle over the horizon."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        predictions = [self._cycle[i % self.season] for i in range(horizon)]
        return ForecastResult(self.name, "", "", horizon, predictions,
                              len(self._cycle), {"season": self.season})


class MovingAverage:
    """Forecast the mean of the trailing window."""

    name = "moving_average"

    def __init__(self, window: int = 7) -> None:
        if window < 1:
            raise ValueError("Window must be at least 1.")
        self.window = window
        self._level = 0.0
        self._length = 0

    def fit(self, history: list[float] | np.ndarray) -> "MovingAverage":
        """Fit on history (stores the trailing-window mean)."""
        values = _as_array(history)
        if len(values) < self.window:
            raise InsufficientHistoryError(
                f"Moving average (window={self.window}) needs at least "
                f"{self.window} observations, got {len(values)}."
            )
        self._level = float(np.mean(values[-self.window:]))
        self._length = len(values)
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Forecast a flat line at the trailing mean."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        return ForecastResult(self.name, "", "", horizon,
                              [self._level] * horizon, self._length,
                              {"window": self.window})


class Drift:
    """Extrapolate the average per-period change (trend baseline)."""

    name = "drift"

    def __init__(self) -> None:
        self._last = 0.0
        self._slope = 0.0
        self._length = 0

    def fit(self, history: list[float] | np.ndarray) -> "Drift":
        """Fit on history (stores last value and mean slope)."""
        values = _as_array(history)
        if len(values) < 2:
            raise InsufficientHistoryError("Drift needs at least 2 observations.")
        self._last = float(values[-1])
        self._slope = float((values[-1] - values[0]) / (len(values) - 1))
        self._length = len(values)
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Extrapolate the linear drift over the horizon."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        predictions = [self._last + self._slope * step for step in range(1, horizon + 1)]
        return ForecastResult(self.name, "", "", horizon, predictions, self._length)


class SimpleExponentialSmoothing:
    """Classical level-only exponential smoothing."""

    name = "ses"

    def __init__(self, alpha: float = 0.3) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("Alpha must be in (0, 1].")
        self.alpha = alpha
        self._level = 0.0
        self._length = 0

    def fit(self, history: list[float] | np.ndarray) -> "SimpleExponentialSmoothing":
        """Fit the smoothing level over history."""
        values = _as_array(history)
        level = float(values[0])
        for value in values[1:]:
            level = self.alpha * float(value) + (1.0 - self.alpha) * level
        self._level = level
        self._length = len(values)
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Forecast a flat line at the smoothed level."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        return ForecastResult(self.name, "", "", horizon,
                              [self._level] * horizon, self._length,
                              {"alpha": self.alpha})


BASELINE_MODELS: dict[str, type] = {
    "naive": Naive,
    "seasonal_naive": SeasonalNaive,
    "moving_average": MovingAverage,
    "drift": Drift,
    "ses": SimpleExponentialSmoothing,
}
