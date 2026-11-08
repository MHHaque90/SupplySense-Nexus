"""Controlled Monte Carlo simulation (Phase 8).

Each iteration samples ONLY explicitly configured uncertain
parameters (duration, supply reduction, delay, demand multiplier)
using a seeded NumPy generator — never global random state. Same
inputs plus same seed reproduce the same results; different seeds may
vary. Percentiles are exposed only when the simulation count is
sufficient (documented minimums in SimulationConfig).
"""

import numpy as np

from backend.app.analytics.simulation.types import (
    DEFAULT_SIMULATION_CONFIG,
    DistributionAssumption,
    SimulationConfig,
)


def sample_parameters(
    assumptions: list[DistributionAssumption],
    rng: np.random.Generator,
    count: int,
) -> dict[str, np.ndarray]:
    """Sample each configured distribution; fixed params pass through."""
    from backend.app.analytics.simulation import probability as probability_mod

    sampled: dict[str, np.ndarray] = {}
    for assumption in assumptions:
        probability_mod.validate_distribution(assumption)
        sampled[assumption.parameter] = probability_mod.sample_distribution(
            assumption, rng, count
        )
    return sampled


def run_iterations(
    run_once,
    sampled: dict[str, np.ndarray],
    count: int,
) -> list[dict[str, np.ndarray]]:
    """Execute the deterministic engine once per sampled parameter set."""
    return [run_once({name: values[index] for name, values in sampled.items()})
            for index in range(count)]


def distribution_stats(
    values: list[float] | np.ndarray,
    count: int,
    config: SimulationConfig | None = None,
) -> dict[str, float | None]:
    """Summarize Monte Carlo outputs with count-gated percentiles."""
    config = config or DEFAULT_SIMULATION_CONFIG
    data = np.asarray(values, dtype=float)
    if len(data) == 0:
        raise ValueError("No simulation outputs to summarize.")
    stats: dict[str, float | None] = {
        "mean": float(np.mean(data)),
        "median": float(np.median(data)),
        "min": float(np.min(data)),
        "max": float(np.max(data)),
        "p05": None, "p25": None, "p50": None,
        "p75": None, "p90": None, "p95": None, "p99": None,
    }
    if count >= config.min_simulations_percentiles:
        for name, level in (("p05", 5), ("p25", 25), ("p50", 50),
                            ("p75", 75), ("p90", 90), ("p95", 95)):
            stats[name] = float(np.percentile(data, level))
    if count >= config.min_simulations_tail:
        stats["p99"] = float(np.percentile(data, 99))
        # p90/p95 already set above; tail gate additionally confirms them.
    return stats


def stockout_probability(stockout_flags: list[bool]) -> float:
    """Fraction of iterations with any stockout day."""
    if not stockout_flags:
        raise ValueError("No iterations to summarize.")
    return float(sum(1 for flag in stockout_flags if flag) / len(stockout_flags))


def make_generator(seed: int) -> np.random.Generator:
    """Build an explicit seeded generator (no global state)."""
    return np.random.default_rng(seed)


__all__ = [
    "sample_parameters",
    "run_iterations",
    "distribution_stats",
    "stockout_probability",
    "make_generator",
]
