"""Trend assessment and seasonality detection (Phase 4).

Trend builds on the Phase 3 slope helper and adds direction,
normalized slope, and an R-squared strength indicator. Seasonality
detection requires sufficient history and never declares seasonal
structure from too few observations. Correlation is reported as
association only — never as causation.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TrendAssessment:
    """Direction, slope, and strength of a series trend."""

    direction: str  # "up", "down", or "flat"
    slope_per_day: float
    normalized_slope: float | None  # slope scaled by mean level
    r_squared: float  # goodness of linear fit in [0, 1]
    observations: int

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view of the assessment."""
        return {
            "direction": self.direction,
            "slope_per_day": self.slope_per_day,
            "normalized_slope": self.normalized_slope,
            "r_squared": self.r_squared,
            "observations": self.observations,
        }


def assess_trend(values: list[float] | np.ndarray) -> TrendAssessment:
    """Assess linear trend direction, slope, and fit strength."""
    data = np.asarray(values, dtype=float).ravel()
    total = len(data)
    if total < 3 or np.all(data == data[0]):
        return TrendAssessment("flat", 0.0, 0.0 if total else None, 0.0, total)
    positions = np.arange(total)
    slope, intercept = np.polyfit(positions, data, 1)
    fitted = intercept + slope * positions
    residual_sum = float(np.sum((data - fitted) ** 2))
    total_sum = float(np.sum((data - np.mean(data)) ** 2))
    r_squared = 0.0 if total_sum == 0 else max(0.0, 1.0 - residual_sum / total_sum)
    mean = float(np.mean(data))
    normalized = float(slope / mean) if mean > 0 else None
    significant = abs(slope) * total / mean >= 0.3 if mean > 0 else False
    direction = "flat" if not significant else ("up" if slope > 0 else "down")
    return TrendAssessment(direction, float(slope), normalized, float(r_squared), total)


@dataclass(frozen=True)
class SeasonalityFinding:
    """Detected seasonal period with supporting evidence."""

    period: int | None
    strength: float | None  # weekday/weekend-style gap in [0, 1+]
    observations: int
    sufficient_history: bool

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable view of the finding."""
        return {
            "period": self.period,
            "strength": self.strength,
            "observations": self.observations,
            "sufficient_history": self.sufficient_history,
        }


def detect_seasonality(
    values: list[float] | np.ndarray,
    dates: pd.DatetimeIndex | list[object] | None = None,
    periods: tuple[int, ...] = (7, 14, 28),
    threshold: float = 0.25,
) -> SeasonalityFinding:
    """Detect the strongest supported seasonal period, if any.

    Weekly-style periods compare weekday vs weekend means; longer
    periods compare first-half vs second-half cycle means. A period is
    eligible only with at least two full cycles of history.
    """
    data = np.asarray(values, dtype=float).ravel()
    total = len(data)
    if dates is None:
        stamps = pd.DatetimeIndex(pd.date_range(end="2026-06-30", periods=max(total, 1), freq="D"))
    else:
        stamps = pd.DatetimeIndex(dates)
    best: int | None = None
    best_strength: float | None = None
    for period in sorted(periods):
        if total < 2 * period:
            continue
        frame = pd.DataFrame({"quantity": data[-2 * period:] if period > 7 else data})
        if period == 7:
            segment_dates = stamps[-len(frame):]
            weekday = frame[pd.DatetimeIndex(segment_dates).weekday < 5]["quantity"].mean()
            weekend = frame[pd.DatetimeIndex(segment_dates).weekday >= 5]["quantity"].mean()
            if pd.isna(weekday) or weekday == 0:
                continue
            strength = abs(float(weekday) - float(weekend)) / float(weekday)
        else:
            cycle = np.asarray(frame["quantity"].to_numpy(), dtype=float)
            half = len(cycle) // 2
            first, second = float(np.mean(cycle[:half])), float(np.mean(cycle[half: 2 * half]))
            if first == 0:
                continue
            strength = abs(first - second) / abs(first)
        if strength >= threshold and (best_strength is None or strength > best_strength):
            best, best_strength = period, float(strength)
    return SeasonalityFinding(
        period=best,
        strength=best_strength,
        observations=total,
        sufficient_history=total >= 2 * min(periods),
    )
