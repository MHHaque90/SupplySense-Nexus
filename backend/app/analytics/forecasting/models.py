"""Phase 4 forecasting models: statistical, intermittent, and ML layers.

All models share the Phase 3 ``fit(history)`` / ``predict(horizon)``
interface. Smoothing parameters are fixed, documented defaults (no
optimizer fitting), which keeps results deterministic, fast, and
explainable. Demand is non-negative; raw model outputs are NOT floored
here — flooring happens once in the forecast output contract so
backtest metrics stay honest.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from backend.app.analytics.forecasting.baselines import _as_array
from backend.app.analytics.forecasting.result import ForecastResult
from backend.app.analytics.types import InsufficientHistoryError

MODEL_VERSION = "4.0.0"


class ZeroForecast:
    """Deterministic zero forecast for all-zero demand series."""

    name = "zero"

    def __init__(self) -> None:
        self._length = 0

    def fit(self, history: list[float] | np.ndarray) -> "ZeroForecast":
        """Accept any history (including empty of signal)."""
        values = np.asarray(history, dtype=float).ravel()
        self._length = len(values)
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Forecast zeros over the horizon."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        return ForecastResult(self.name, "", "", horizon, [0.0] * horizon, self._length)


class HoltTrend:
    """Holt's linear trend (level + trend exponential smoothing)."""

    name = "holt"

    def __init__(self, alpha: float = 0.3, beta: float = 0.1) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("Alpha must be in (0, 1].")
        if not 0.0 < beta <= 1.0:
            raise ValueError("Beta must be in (0, 1].")
        self.alpha = alpha
        self.beta = beta
        self._level = 0.0
        self._trend = 0.0
        self._length = 0

    def fit(self, history: list[float] | np.ndarray) -> "HoltTrend":
        """Fit level and trend recursions over history."""
        values = _as_array(history)
        if len(values) < 4:
            raise InsufficientHistoryError(
                f"Holt trend needs at least 4 observations, got {len(values)}."
            )
        level = float(values[0])
        trend = float(values[1] - values[0])
        for value in values[1:]:
            previous_level = level
            level = self.alpha * float(value) + (1.0 - self.alpha) * (level + trend)
            trend = self.beta * (level - previous_level) + (1.0 - self.beta) * trend
        self._level = level
        self._trend = trend
        self._length = len(values)
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Extrapolate level plus trend over the horizon."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        predictions = [self._level + self._trend * step for step in range(1, horizon + 1)]
        return ForecastResult(
            self.name, "", "", horizon, predictions, self._length,
            {"alpha": self.alpha, "beta": self.beta},
        )


class HoltWinters:
    """Additive Holt-Winters (level + trend + seasonal)."""

    name = "holt_winters"

    def __init__(self, season: int = 7, alpha: float = 0.3, beta: float = 0.1, gamma: float = 0.3) -> None:
        if season < 2:
            raise ValueError("Season must be at least 2.")
        if not 0.0 < alpha <= 1.0 or not 0.0 < beta <= 1.0 or not 0.0 < gamma <= 1.0:
            raise ValueError("Smoothing parameters must be in (0, 1].")
        self.season = season
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self._level = 0.0
        self._trend = 0.0
        self._seasonal: list[float] = []
        self._length = 0

    def fit(self, history: list[float] | np.ndarray) -> "HoltWinters":
        """Fit level, trend, and seasonal components (needs 2 full seasons)."""
        values = _as_array(history)
        season = self.season
        if len(values) < 2 * season:
            raise InsufficientHistoryError(
                f"Holt-Winters (season={season}) needs at least {2 * season} "
                f"observations, got {len(values)}."
            )
        first_avg = float(np.mean(values[:season]))
        second_avg = float(np.mean(values[season: 2 * season]))
        level = first_avg
        trend = (second_avg - first_avg) / season
        seasonal = [float(values[i] - first_avg) for i in range(season)]
        for position in range(len(values)):
            value = float(values[position])
            slot = position % season
            previous_level = level
            level = (
                self.alpha * (value - seasonal[slot])
                + (1.0 - self.alpha) * (level + trend)
            )
            trend = self.beta * (level - previous_level) + (1.0 - self.beta) * trend
            seasonal[slot] = (
                self.gamma * (value - level) + (1.0 - self.gamma) * seasonal[slot]
            )
        self._level = level
        self._trend = trend
        self._seasonal = seasonal
        self._length = len(values)
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Extrapolate level, trend, and seasonal pattern."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        base = self._length
        predictions = [
            self._level + self._trend * step + self._seasonal[(base + step - 1) % self.season]
            for step in range(1, horizon + 1)
        ]
        return ForecastResult(
            self.name, "", "", horizon, predictions, self._length,
            {"season": self.season, "alpha": self.alpha, "beta": self.beta, "gamma": self.gamma},
        )


class AutoRegressor:
    """Autoregressive AR(p) model fit by ordinary least squares."""

    name = "autoreg"

    def __init__(self, order: int = 7) -> None:
        if order < 1:
            raise ValueError("Order must be at least 1.")
        self.order = order
        self._intercept = 0.0
        self._coefficients: list[float] = []
        self._tail: list[float] = []
        self._length = 0

    def fit(self, history: list[float] | np.ndarray) -> "AutoRegressor":
        """Fit AR coefficients by least squares (needs 2p + 4 observations)."""
        values = _as_array(history)
        order = self.order
        if len(values) < 2 * order + 4:
            raise InsufficientHistoryError(
                f"AR({order}) needs at least {2 * order + 4} observations, "
                f"got {len(values)}."
            )
        rows = len(values) - order
        design = np.column_stack(
            [np.ones(rows)] + [values[order - lag - 1: rows + order - lag - 1] for lag in range(order)]
        )
        target = values[order:]
        solution, _, _, _ = np.linalg.lstsq(design, target, rcond=None)
        self._intercept = float(solution[0])
        self._coefficients = [float(c) for c in solution[1:]]
        self._tail = [float(v) for v in values[-order:]]
        self._length = len(values)
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Recursively extend the series over the horizon."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        if not self._coefficients:
            raise InsufficientHistoryError("AutoRegressor is not fitted.")
        window = list(self._tail)
        predictions = []
        for _ in range(horizon):
            value = self._intercept + sum(
                coef * window[-lag - 1] for lag, coef in enumerate(self._coefficients)
            )
            predictions.append(float(value))
            window.append(float(value))
        return ForecastResult(
            self.name, "", "", horizon, predictions, self._length, {"order": self.order}
        )


class Croston:
    """Croston-style intermittent-demand forecast.

    Smooths non-zero demand sizes and inter-demand intervals separately
    (alpha = 0.1 default) and forecasts size/interval per period.
    Assumptions: demand occurrences are stationary; per-period rate is
    the right quantity for days-of-supply planning. All-zero history
    yields a deterministic zero forecast; no division by zero occurs
    because the interval estimate is floored at one day.
    """

    name = "croston"

    def __init__(self, alpha: float = 0.1) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("Alpha must be in (0, 1].")
        self.alpha = alpha
        self._rate = 0.0
        self._length = 0

    def fit(self, history: list[float] | np.ndarray) -> "Croston":
        """Fit size and interval smoothers over history."""
        values = _as_array(history)
        if len(values) < 2:
            raise InsufficientHistoryError("Croston needs at least 2 observations.")
        nonzero = values[values > 0]
        if len(nonzero) == 0:
            self._rate = 0.0
            self._length = len(values)
            return self
        size = float(nonzero[0])
        interval = 1.0
        gap = 0
        for value in values:
            gap += 1
            if value > 0:
                size = self.alpha * float(value) + (1.0 - self.alpha) * size
                interval = self.alpha * gap + (1.0 - self.alpha) * interval
                gap = 0
        interval = max(1.0, interval)
        self._rate = size / interval
        self._length = len(values)
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Forecast a flat per-period rate over the horizon."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        return ForecastResult(
            self.name, "", "", horizon, [self._rate] * horizon, self._length,
            {"alpha": self.alpha},
        )


ML_FEATURE_COLUMNS = [
    "lag_1", "lag_7", "lag_14", "lag_28",
    "rolling_mean_7", "rolling_mean_14", "rolling_mean_28",
    "rolling_std_7", "rolling_std_28",
    "day_of_week", "month", "is_weekend", "days_since_nonzero",
]


def _ml_frame(values: np.ndarray, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Build the leakage-safe ML feature frame for one series.

    Every feature at row T uses observations strictly before T: lags
    are shifted, rolling statistics use ``min_periods`` on shifted data,
    and calendar fields derive from the date alone.
    """
    frame = pd.DataFrame({"quantity": values}, index=dates)
    for lag in (1, 7, 14, 28):
        frame[f"lag_{lag}"] = frame["quantity"].shift(lag)
    shifted = frame["quantity"].shift(1)
    for window in (7, 14, 28):
        frame[f"rolling_mean_{window}"] = shifted.rolling(window, min_periods=1).mean()
    for window in (7, 28):
        frame[f"rolling_std_{window}"] = shifted.rolling(window, min_periods=2).std(ddof=0)
    frame["day_of_week"] = frame.index.weekday
    frame["month"] = frame.index.month
    frame["is_weekend"] = (frame.index.weekday >= 5).astype(int)
    elapsed: float | None = None
    gaps: list[float] = []
    for value in values.tolist():
        gaps.append(float("nan") if elapsed is None else float(elapsed + 1))
        elapsed = 0 if value > 0 else (None if elapsed is None else elapsed + 1)
    frame["days_since_nonzero"] = gaps
    return frame


class GradientBoostingForecaster:
    """HistGradientBoosting recursive forecaster (random_state=0).

    Trains only on rows whose features are fully observed (no NaN
    leakage padding) and extends recursively: each predicted step
    becomes history for the next step's features. Temporal order is
    never shuffled.
    """

    name = "hgb"

    def __init__(self, random_state: int = 0, max_iter: int = 200) -> None:
        self.random_state = random_state
        self.max_iter = max_iter
        self._model: HistGradientBoostingRegressor | None = None
        self._history: list[float] = []
        self._last_date: pd.Timestamp | None = None

    def fit(
        self,
        history: list[float] | np.ndarray,
        dates: pd.DatetimeIndex | None = None,
    ) -> "GradientBoostingForecaster":
        """Fit on history with leakage-safe features (needs 90 observations)."""
        values = _as_array(history)
        if len(values) < 90:
            raise InsufficientHistoryError(
                f"Gradient boosting needs at least 90 observations, got {len(values)}."
            )
        if dates is None:
            dates = pd.date_range(end=pd.Timestamp.today().normalize(), periods=len(values), freq="D")
        frame = _ml_frame(values, pd.DatetimeIndex(dates[-len(values):]))
        train = frame.dropna(subset=ML_FEATURE_COLUMNS)
        if len(train) < 30:
            raise InsufficientHistoryError("Not enough complete feature rows to train.")
        self._model = HistGradientBoostingRegressor(
            max_iter=self.max_iter, early_stopping=False, random_state=self.random_state
        )
        self._model.fit(train[ML_FEATURE_COLUMNS], train["quantity"])
        self._history = [float(v) for v in values]
        self._last_date = pd.Timestamp(frame.index[-1])
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Recursively forecast step by step over the horizon."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        if self._model is None or self._last_date is None:
            raise InsufficientHistoryError("GradientBoostingForecaster is not fitted.")
        extended = list(self._history)
        history_dates = [
            self._last_date - pd.Timedelta(days=len(extended) - 1 - i)
            for i in range(len(extended))
        ]
        future_dates = pd.date_range(self._last_date + pd.Timedelta(days=1), periods=horizon, freq="D")
        predictions: list[float] = []
        for step_date in future_dates:
            # Placeholder row AT the future date: every feature of that
            # row then uses observations strictly before the step.
            frame = _ml_frame(
                np.asarray(extended + [0.0]),
                pd.DatetimeIndex(history_dates + [step_date]),
            )
            row = frame.iloc[[-1]][ML_FEATURE_COLUMNS]
            value = float(self._model.predict(row)[0])
            predictions.append(value)
            extended.append(value)
            history_dates.append(step_date)
        return ForecastResult(
            self.name, "", "", horizon, predictions, len(self._history),
            {"random_state": self.random_state, "max_iter": self.max_iter},
        )


PHASE4_MODELS: dict[str, type] = {
    "zero": ZeroForecast,
    "holt": HoltTrend,
    "holt_winters": HoltWinters,
    "autoreg": AutoRegressor,
    "croston": Croston,
    "hgb": GradientBoostingForecaster,
}
