"""Phase 8 Monte Carlo tests: seeds, counts, percentiles, distributions."""

import numpy as np
import pytest

from backend.app.analytics.simulation import monte_carlo
from backend.app.analytics.simulation.types import DistributionAssumption


def test_same_seed_same_results():
    first = monte_carlo.make_generator(42).uniform(0.0, 1.0, 50)
    second = monte_carlo.make_generator(42).uniform(0.0, 1.0, 50)
    assert np.array_equal(first, second)


def test_different_seed_allowed_variation():
    first = monte_carlo.make_generator(42).uniform(0.0, 1.0, 50)
    second = monte_carlo.make_generator(43).uniform(0.0, 1.0, 50)
    assert not np.array_equal(first, second)


def test_simulation_count_and_percentile_gating():
    stats = monte_carlo.distribution_stats(list(range(10)), 10)
    assert stats["mean"] == 4.5
    assert stats["p90"] is None  # below the 20-run minimum
    assert stats["p99"] is None
    stats = monte_carlo.distribution_stats(list(range(30)), 30)
    assert stats["p90"] is not None and stats["p95"] is not None
    assert stats["p99"] is None  # below the 100-run tail minimum
    stats = monte_carlo.distribution_stats(list(range(120)), 120)
    assert stats["p99"] is not None
    with pytest.raises(ValueError):
        monte_carlo.distribution_stats([], 0)


def test_distribution_outputs_bounded():
    triangular = DistributionAssumption(
        parameter="duration_days", distribution="triangular",
        minimum=7.0, mode=14.0, maximum=21.0, units="days",
    )
    rng = monte_carlo.make_generator(7)
    samples = monte_carlo.sample_parameters([triangular], rng, 200)
    assert set(samples) == {"duration_days"}
    assert samples["duration_days"].min() >= 7.0
    assert samples["duration_days"].max() <= 21.0


def test_deterministic_event_behavior_without_distributions():
    rng = monte_carlo.make_generator(1)
    assert monte_carlo.sample_parameters([], rng, 5) == {}


def test_stockout_probability():
    assert monte_carlo.stockout_probability([True, False, True, False]) == 0.5
    with pytest.raises(ValueError):
        monte_carlo.stockout_probability([])


def test_run_iterations_uses_sampled_params():
    seen = []

    def _run_once(params):
        seen.append(dict(params))
        return {"ending": np.array([1.0]), "unmet": np.array([0.0]),
                "stockout_flag": np.array([False])}

    sampled = {"duration_days": np.array([7.0, 14.0, 21.0])}
    results = monte_carlo.run_iterations(_run_once, sampled, 3)
    assert len(results) == 3
    assert [item["duration_days"] for item in seen] == [7.0, 14.0, 21.0]
