"""Forecast evaluation metrics with explicit denominator rules (Phase 3).

Denominator behavior:
- MAE/RMSE/bias: defined for any finite inputs.
- MAPE: zero actuals are masked out; returns NaN when every actual is
  zero. MAPE is misleading for intermittent demand (documented).
- sMAPE: bounded in [0, 2]; the 0/0 point contributes 0.
- WAPE: sums first, so isolated zeros are harmless; undefined (NaN)
  when total actual is zero.
"""

import numpy as np


def _as_arrays(
    actual: list[float] | np.ndarray, predicted: list[float] | np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    actual_arr = np.asarray(actual, dtype=float).ravel()
    predicted_arr = np.asarray(predicted, dtype=float).ravel()
    if actual_arr.shape != predicted_arr.shape:
        raise ValueError(
            f"Length mismatch: {len(actual_arr)} actuals vs {len(predicted_arr)} predictions."
        )
    if actual_arr.size == 0:
        raise ValueError("Empty inputs: metrics need at least one observation.")
    if not np.all(np.isfinite(actual_arr)) or not np.all(np.isfinite(predicted_arr)):
        raise ValueError("Inputs must be finite.")
    return actual_arr, predicted_arr


def mae(actual: list[float] | np.ndarray, predicted: list[float] | np.ndarray) -> float:
    """Mean absolute error."""
    actual_arr, predicted_arr = _as_arrays(actual, predicted)
    return float(np.mean(np.abs(actual_arr - predicted_arr)))


def rmse(actual: list[float] | np.ndarray, predicted: list[float] | np.ndarray) -> float:
    """Root mean squared error."""
    actual_arr, predicted_arr = _as_arrays(actual, predicted)
    return float(np.sqrt(np.mean((actual_arr - predicted_arr) ** 2)))


def mape(actual: list[float] | np.ndarray, predicted: list[float] | np.ndarray) -> float:
    """Mean absolute percentage error with zero masking.

    Returns NaN when all actuals are zero. Prefer WAPE/sMAPE for
    intermittent demand.
    """
    actual_arr, predicted_arr = _as_arrays(actual, predicted)
    nonzero = actual_arr != 0
    if not np.any(nonzero):
        return float("nan")
    return float(np.mean(np.abs((actual_arr[nonzero] - predicted_arr[nonzero]) / actual_arr[nonzero])))


def smape(actual: list[float] | np.ndarray, predicted: list[float] | np.ndarray) -> float:
    """Symmetric MAPE in [0, 2]; 0/0 points contribute 0."""
    actual_arr, predicted_arr = _as_arrays(actual, predicted)
    denominator = (np.abs(actual_arr) + np.abs(predicted_arr)) / 2.0
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(denominator == 0, 0.0, np.abs(actual_arr - predicted_arr) / denominator)
    return float(np.mean(terms))


def wape(actual: list[float] | np.ndarray, predicted: list[float] | np.ndarray) -> float:
    """Weighted absolute percentage error; NaN when total actual is zero."""
    actual_arr, predicted_arr = _as_arrays(actual, predicted)
    total = np.sum(np.abs(actual_arr))
    if total == 0:
        return float("nan")
    return float(np.sum(np.abs(actual_arr - predicted_arr)) / total)


def bias(actual: list[float] | np.ndarray, predicted: list[float] | np.ndarray) -> float:
    """Mean forecast error (positive means systematic over-forecast)."""
    actual_arr, predicted_arr = _as_arrays(actual, predicted)
    return float(np.mean(predicted_arr - actual_arr))


METRICS: dict[str, object] = {
    "mae": mae,
    "rmse": rmse,
    "mape": mape,
    "smape": smape,
    "wape": wape,
    "bias": bias,
}


def score_all(
    actual: list[float] | np.ndarray, predicted: list[float] | np.ndarray
) -> dict[str, float]:
    """Compute every metric for one actual/prediction pair."""
    return {name: float(func(actual, predicted)) for name, func in METRICS.items()}  # type: ignore[operator]
