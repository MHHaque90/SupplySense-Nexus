"""Probability handling with explicit provenance (Phase 8).

Modes: deterministic (conditioned on occurrence, labeled
DETERMINISTIC_SCENARIO, never a real-world 100%), explicit
(USER_ASSUMED with bounds checking), empirical (contract present but
unavailable — no validated historical disruption-frequency data
exists), and distribution assumptions (triangular/uniform sampled with
explicit seeded generators).

Phase 7 risk severity is NEVER converted into a probability.
"""

import numpy as np

from backend.app.analytics.simulation.types import DistributionAssumption


class EmpiricalUnavailableError(ValueError):
    """Raised when empirical probability is requested without data."""


def resolve_probability(mode: str, probability: float | None) -> tuple[float, str]:
    """Resolve (probability, source) for deterministic/explicit modes."""
    if mode == "deterministic":
        return 1.0, "DETERMINISTIC"
    if mode == "explicit":
        if probability is None:
            raise ValueError("Explicit mode requires a probability value.")
        if not 0.0 <= probability <= 1.0:
            raise ValueError(f"Probability {probability} outside [0, 1].")
        return float(probability), "USER_ASSUMED"
    if mode == "empirical":
        raise EmpiricalUnavailableError(
            "Empirical mode is unavailable: no validated historical "
            "disruption-frequency data exists. Use deterministic or explicit."
        )
    raise ValueError(
        f"Unknown probability mode: {mode}. Valid: deterministic, explicit, empirical."
    )


def describe_probability(mode: str, probability: float, source: str) -> str:
    """Describe probability in scenario language (never as prediction)."""
    if mode == "deterministic":
        return (
            "Conditional outcome if the disruption event occurs "
            "(DETERMINISTIC_SCENARIO; not a real-world 100% probability)."
        )
    return (
        f"{probability:.0%} user-assumed scenario probability "
        f"({source}); not predicted or empirically validated."
    )


def sample_distribution(
    assumption: DistributionAssumption,
    rng: np.random.Generator,
    count: int,
) -> np.ndarray:
    """Sample an uncertain scenario parameter deterministically."""
    if assumption.distribution == "uniform":
        if assumption.maximum < assumption.minimum:
            raise ValueError(f"Uniform maximum below minimum for {assumption.parameter}.")
        return rng.uniform(assumption.minimum, assumption.maximum, count)
    if assumption.distribution == "triangular":
        if not assumption.minimum <= assumption.mode <= assumption.maximum:
            raise ValueError(f"Triangular bounds inconsistent for {assumption.parameter}.")
        return rng.triangular(assumption.minimum, assumption.mode, assumption.maximum, count)
    raise ValueError(
        f"Unsupported distribution: {assumption.distribution}. Valid: triangular, uniform."
    )


def validate_distribution(assumption: DistributionAssumption) -> None:
    """Validate a distribution assumption's parameters."""
    sample_distribution(assumption, np.random.default_rng(0), 1)
