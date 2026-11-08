"""Supply-side event effects on simulated inbound (Phase 8).

All effects operate on copies of the baseline inbound schedule inside
simulation state. Historical PO/shipment rows are never modified.

- SUPPLIER_DISRUPTION: arrivals from targeted supplier relationships
  during the window are scaled by (1 - supply_reduction).
- SHIPMENT_DELAY / LEAD_TIME_DELAY: arrivals shift later by the delay.
- SUPPLY_REDUCTION: all in-window arrivals scaled by (1 - reduction).
- WAREHOUSE_DISRUPTION: handled by the engine via availability flags.
- COMBINED_DISRUPTION: components applied in a fixed documented order:
  supplier zeroing, then reduction scaling, then delay shifting.
"""

import numpy as np


def _in_window(index: int, start: int, duration: int) -> bool:
    return start <= index < start + duration


def apply_supplier_disruption(
    arrivals: np.ndarray,
    supplier_of_arrival: list[str | None],
    targeted_suppliers: list[str],
    supply_reduction: float,
    start: int,
    duration: int,
) -> tuple[np.ndarray, dict[str, float]]:
    """Scale targeted arrivals during the window; report unavailable qty."""
    result = arrivals.astype(float).copy()
    unavailable = 0.0
    targets = set(targeted_suppliers)
    for index in range(len(result)):
        if _in_window(index, start, duration) and supplier_of_arrival[index] in targets:
            removed = result[index] * supply_reduction
            unavailable += removed
            result[index] -= removed
    return result, {"unavailable_inbound_quantity": float(unavailable)}


def apply_supply_reduction(
    arrivals: np.ndarray,
    supply_reduction: float,
    start: int,
    duration: int,
) -> tuple[np.ndarray, dict[str, float]]:
    """Scale all in-window arrivals by (1 - reduction)."""
    result = arrivals.astype(float).copy()
    unavailable = 0.0
    for index in range(len(result)):
        if _in_window(index, start, duration):
            removed = result[index] * supply_reduction
            unavailable += removed
            result[index] -= removed
    return result, {"unavailable_inbound_quantity": float(unavailable)}


def apply_arrival_delay(
    arrivals: np.ndarray,
    delay_days: int,
    start: int,
    duration: int,
    targeted_only: np.ndarray | None = None,
) -> tuple[np.ndarray, dict[str, float]]:
    """Shift in-window arrivals later by the delay (clipped at horizon)."""
    if delay_days < 0:
        raise ValueError("delay_days must be non-negative.")
    result = np.zeros_like(arrivals, dtype=float)
    delayed_quantity = 0.0
    mask = np.ones(len(arrivals), dtype=bool) if targeted_only is None else np.asarray(
        targeted_only, dtype=bool
    )
    for index in range(len(arrivals)):
        quantity = float(arrivals[index])
        if _in_window(index, start, duration) and mask[index] and delay_days:
            target = min(index + delay_days, len(arrivals) - 1)
            result[target] += quantity
            delayed_quantity += quantity
        else:
            result[index] += quantity
    return result, {"delayed_inbound_quantity": float(delayed_quantity)}


def apply_combined(
    arrivals: np.ndarray,
    supplier_of_arrival: list[str | None],
    targeted_suppliers: list[str],
    supply_reduction: float,
    delay_days: int,
    start: int,
    duration: int,
) -> tuple[np.ndarray, dict[str, float]]:
    """Apply supplier scaling, then reduction scaling, then delay shifting."""
    step, first = apply_supplier_disruption(
        arrivals, supplier_of_arrival, targeted_suppliers, supply_reduction, start, duration
    )
    step, third = apply_arrival_delay(step, delay_days, start, duration)
    merged = {
        "unavailable_inbound_quantity": float(first["unavailable_inbound_quantity"]),
        "delayed_inbound_quantity": float(third["delayed_inbound_quantity"]),
    }
    return step, merged
