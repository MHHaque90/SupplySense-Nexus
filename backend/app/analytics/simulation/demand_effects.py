"""Demand-side event effects (Phase 8).

Applies the demand multiplier to baseline demand series (point, lower,
and upper together, documented). The Phase 4 forecast itself is never
retouched — the multiplier acts on a copy inside simulation state only.
"""

import numpy as np


def apply_demand_multiplier(
    point: list[float] | np.ndarray,
    lower: list[float] | np.ndarray,
    upper: list[float] | np.ndarray,
    multiplier: float,
    start_index: int = 0,
    end_index: int | None = None,
) -> tuple[list[float], list[float], list[float]]:
    """Scale demand series by the multiplier over [start_index, end_index)."""
    if multiplier <= 0:
        raise ValueError("demand_multiplier must be positive.")
    point_arr = np.asarray(point, dtype=float)
    lower_arr = np.asarray(lower, dtype=float)
    upper_arr = np.asarray(upper, dtype=float)
    end = len(point_arr) if end_index is None else min(end_index, len(point_arr))
    shocked_point = point_arr.copy()
    shocked_lower = lower_arr.copy()
    shocked_upper = upper_arr.copy()
    shocked_point[start_index:end] *= multiplier
    shocked_lower[start_index:end] *= multiplier
    shocked_upper[start_index:end] *= multiplier
    shocked_point = np.maximum(shocked_point, 0.0)
    shocked_lower = np.maximum(shocked_lower, 0.0)
    shocked_upper = np.maximum(shocked_upper, 0.0)
    return shocked_point.tolist(), shocked_lower.tolist(), shocked_upper.tolist()
