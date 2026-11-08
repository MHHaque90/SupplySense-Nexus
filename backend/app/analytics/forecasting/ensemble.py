"""Simple ensembles compared like any other model (Phase 4).

Only equal-weight averaging and inverse-error weighting are offered.
An ensemble is selected only when walk-forward validation supports it;
it is never applied automatically.
"""

import numpy as np

from backend.app.analytics.forecasting.result import ForecastResult
from backend.app.analytics.types import InsufficientHistoryError


def inverse_error_weights(scores: dict[str, float]) -> dict[str, float]:
    """Convert mean validation errors into normalized inverse weights."""
    finite = {name: score for name, score in scores.items() if score is not None and score >= 0}
    if not finite:
        raise ValueError("No finite scores available for weighting.")
    if all(score == 0 for score in finite.values()):
        equal = 1.0 / len(finite)
        return {name: equal for name in finite}
    raw = {name: 1.0 / (score + 1e-9) for name, score in finite.items()}
    total = sum(raw.values())
    return {name: value / total for name, value in raw.items()}


class AverageEnsemble:
    """Equal-weight average of member forecasts."""

    name = "ensemble_average"

    def __init__(self, members: dict[str, object]) -> None:
        if len(members) < 2:
            raise ValueError("Ensembles need at least two members.")
        self.members = members
        self._fitted: dict[str, object] = {}
        self._length = 0

    def fit(self, history: list[float] | np.ndarray) -> "AverageEnsemble":
        """Fit every member on the same history."""
        values = np.asarray(history, dtype=float).ravel()
        if values.size == 0:
            raise InsufficientHistoryError("Empty history: cannot fit ensemble.")
        fitted = {}
        for name, model in self.members.items():
            fitted[name] = model.fit(values)  # type: ignore[attr-defined]
        self._fitted = fitted
        self._length = len(values)
        return self

    def predict(self, horizon: int) -> ForecastResult:
        """Average member predictions point by point."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        if not self._fitted:
            raise InsufficientHistoryError("Ensemble is not fitted.")
        member_forecasts = [
            model.predict(horizon).predictions  # type: ignore[attr-defined]
            for model in self._fitted.values()
        ]
        predictions = [
            float(np.mean([series[step] for series in member_forecasts]))
            for step in range(horizon)
        ]
        return ForecastResult(
            self.name, "", "", horizon, predictions, self._length,
            {"members": sorted(self._fitted)},
        )


class WeightedEnsemble(AverageEnsemble):
    """Inverse-error-weighted average of member forecasts."""

    name = "ensemble_weighted"

    def __init__(self, members: dict[str, object], weights: dict[str, float]) -> None:
        super().__init__(members)
        if set(weights) != set(members):
            raise ValueError("Weights must cover exactly the member models.")
        if abs(sum(weights.values()) - 1.0) > 1e-6:
            raise ValueError("Weights must sum to 1.")
        self.weights = dict(weights)

    def predict(self, horizon: int) -> ForecastResult:
        """Weight member predictions point by point."""
        if horizon < 1:
            raise ValueError("Horizon must be at least 1.")
        if not self._fitted:
            raise InsufficientHistoryError("Ensemble is not fitted.")
        names = sorted(self._fitted)
        member_forecasts = {
            name: self._fitted[name].predict(horizon).predictions  # type: ignore[attr-defined]
            for name in names
        }
        predictions = [
            float(sum(self.weights[name] * member_forecasts[name][step] for name in names))
            for step in range(horizon)
        ]
        return ForecastResult(
            self.name, "", "", horizon, predictions, self._length,
            {"members": names, "weights": self.weights},
        )
