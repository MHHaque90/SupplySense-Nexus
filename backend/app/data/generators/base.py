"""Shared deterministic utilities for synthetic data generators."""

import random
from datetime import date
from typing import Any


def stream_rng(seed: int, *stream: str) -> random.Random:
    """Return an independent deterministic RNG for a named stream.

    Deriving one RNG per stream from the master seed keeps each entity
    type reproducible regardless of generation order.
    """
    return random.Random(f"{seed}:{':'.join(stream)}")


def format_quantity(value: float) -> str:
    """Format a quantity as the string the schema stores."""
    return str(max(0, int(round(value))))


def format_cost(value: float) -> str:
    """Format a monetary value with two decimals as stored by the schema."""
    return f"{max(0.0, value):.2f}"


def format_probability(value: float) -> str:
    """Clamp a probability to [0, 1] and format it as stored."""
    return f"{min(1.0, max(0.0, value)):.2f}"


def opening_balance(average_daily_demand: float, coverage_days: int) -> int:
    """Compute deterministic opening inventory from the shared policy."""
    return max(1, int(round(average_daily_demand * coverage_days)))


def daterange(start: date, end: date) -> list[date]:
    """Return every date from start to end inclusive."""
    days = (end - start).days
    return [start.fromordinal(start.toordinal() + offset) for offset in range(days + 1)]


def business_key(record: dict[str, Any], *fields: str) -> tuple[Any, ...]:
    """Project a record to its deterministic business fields for comparison."""
    return tuple(record[field] for field in fields)
