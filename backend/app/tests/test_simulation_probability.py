"""Phase 8 probability handling tests."""

import pytest

from backend.app.analytics.simulation import probability as probability_mod
from backend.app.analytics.simulation.types import DistributionAssumption


def test_deterministic_mode():
    value, source = probability_mod.resolve_probability("deterministic", None)
    assert value == 1.0 and source == "DETERMINISTIC"
    text = probability_mod.describe_probability("deterministic", 1.0, source)
    assert "Conditional outcome" in text
    assert "not a real-world 100%" in text


def test_explicit_user_assumed_probability():
    value, source = probability_mod.resolve_probability("explicit", 0.2)
    assert value == 0.2 and source == "USER_ASSUMED"
    text = probability_mod.describe_probability("explicit", 0.2, source)
    assert "20%" in text and "user-assumed" in text
    assert "not predicted or empirically validated" in text


def test_probability_bounds():
    with pytest.raises(ValueError):
        probability_mod.resolve_probability("explicit", 1.5)
    with pytest.raises(ValueError):
        probability_mod.resolve_probability("explicit", -0.1)
    with pytest.raises(ValueError):
        probability_mod.resolve_probability("explicit", None)
    with pytest.raises(ValueError):
        probability_mod.resolve_probability(" modelled", 0.5)


def test_probability_provenance_values():
    value, source = probability_mod.resolve_probability("explicit", 0.0)
    assert source in ("DETERMINISTIC", "USER_ASSUMED", "EMPIRICAL", "DISTRIBUTION_ASSUMPTION")
    assert source not in ("PREDICTED", "OBSERVED", "LEARNED", "VALIDATED")


def test_empirical_mode_unavailable():
    with pytest.raises(probability_mod.EmpiricalUnavailableError):
        probability_mod.resolve_probability("empirical", None)


def test_distribution_assumptions():
    import numpy as np

    triangular = DistributionAssumption(
        parameter="duration_days", distribution="triangular",
        minimum=7.0, mode=14.0, maximum=21.0, units="days",
    )
    probability_mod.validate_distribution(triangular)
    rng = np.random.default_rng(42)
    samples = probability_mod.sample_distribution(triangular, rng, 100)
    assert len(samples) == 100
    assert samples.min() >= 7.0 and samples.max() <= 21.0
    uniform = DistributionAssumption(
        parameter="supply_reduction", distribution="uniform",
        minimum=0.2, maximum=0.6, units="fraction",
    )
    samples = probability_mod.sample_distribution(uniform, rng, 50)
    assert samples.min() >= 0.2 and samples.max() <= 0.6
    assert triangular.to_dict()["assumption_status"] == "SCENARIO_ASSUMPTION"


def test_invalid_distributions_rejected():
    import numpy as np

    rng = np.random.default_rng(0)
    bad = DistributionAssumption(
        parameter="duration_days", distribution="triangular",
        minimum=10.0, mode=5.0, maximum=21.0, units="days",
    )
    with pytest.raises(ValueError):
        probability_mod.validate_distribution(bad)
    with pytest.raises(ValueError):
        probability_mod.sample_distribution(
            DistributionAssumption(parameter="x", distribution="normal",
                                   minimum=0.0, maximum=1.0, units=""),
            rng, 5,
        )
