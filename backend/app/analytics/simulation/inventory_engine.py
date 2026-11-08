"""Deterministic daily inventory simulation engine (Phase 8).

Mechanics per day: ending = max(0, beginning + inbound − demand);
unmet = max(0, demand − (beginning + inbound)); stockout_flag =
(ending <= 0 and demand > 0). Unmet demand is tracked explicitly and
never hidden inside negative inventory. Vectorized with NumPy.
"""

import numpy as np


def run_days(
    beginning: float,
    demand: np.ndarray,
    inbound: np.ndarray,
    available_mask: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    """Run the daily engine over one horizon.

    Args:
        beginning: starting on-hand inventory.
        demand: daily demand array.
        inbound: daily inbound array (same length).
        available_mask: boolean array; False days make inventory
            inaccessible (warehouse disruption): demand goes unmet and
            the balance carries unchanged.

    Returns arrays: ending, unmet, stockout_flag.
    """
    demand_arr = np.asarray(demand, dtype=float)
    inbound_arr = np.asarray(inbound, dtype=float)
    if demand_arr.shape != inbound_arr.shape:
        raise ValueError("demand and inbound must share the horizon length.")
    horizon = len(demand_arr)
    mask = np.ones(horizon, dtype=bool) if available_mask is None else np.asarray(
        available_mask, dtype=bool
    )
    ending = np.zeros(horizon)
    unmet = np.zeros(horizon)
    stockout = np.zeros(horizon, dtype=bool)
    balance = float(beginning)
    for day in range(horizon):
        need = float(demand_arr[day])
        if not mask[day]:
            unmet[day] = need
            stockout[day] = need > 0
            ending[day] = balance
            continue
        available = balance + float(inbound_arr[day])
        if available >= need:
            balance = available - need
            unmet[day] = 0.0
        else:
            balance = 0.0
            unmet[day] = need - available
        ending[day] = balance
        stockout[day] = balance <= 0 and need > 0
    return {"ending": ending, "unmet": unmet, "stockout_flag": stockout}


def first_stockout_day(stockout_flag: np.ndarray) -> int | None:
    """Return the first stockout day index, or None when never stocked out."""
    hits = np.flatnonzero(np.asarray(stockout_flag, dtype=bool))
    return int(hits[0]) if len(hits) else None
