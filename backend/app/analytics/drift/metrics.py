"""Deterministic distribution drift metrics for model monitoring.

Provides mathematical divergence metrics comparing reference and current distributions:
- Population Stability Index (PSI): binned quantile distribution shift.
- Kolmogorov-Smirnov (KS): two-sample supremum distance between empirical CDFs.
- Wasserstein Distance: first Wasserstein distance (Earth Mover's Distance).
- Mean Shift: standardized difference in distribution means.
"""

from collections.abc import Sequence

import numpy as np
from scipy import stats


def validate_distribution(
    data: Sequence[float] | np.ndarray,
    name: str,
    min_samples: int = 1,
) -> np.ndarray:
    """Validate and convert an input sequence into a 1D finite numpy float array.

    Raises:
        ValueError: If input has fewer than min_samples or contains non-finite numbers.
    """
    arr = np.asarray(data, dtype=float).ravel()
    if arr.size < min_samples:
        raise ValueError(
            f"{name} distribution must contain at least {min_samples} observation(s), got {arr.size}."
        )
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} distribution contains non-finite values (NaN or Inf).")
    return arr


def population_stability_index(
    reference: Sequence[float] | np.ndarray,
    current: Sequence[float] | np.ndarray,
    num_bins: int = 10,
    epsilon: float = 1e-4,
) -> float:
    """Calculate the Population Stability Index (PSI) between two distributions.

    PSI = sum((q_i - p_i) * ln(q_i / p_i)) where p is reference and q is current.
    Uses reference quantile boundaries with duplicate edge coalescing to guarantee
    strictly monotonic bin intervals.

    Returns:
        float: Deterministic PSI value. 0.0 indicates identical distributions.
    """
    ref_arr = validate_distribution(reference, "Reference", min_samples=1)
    curr_arr = validate_distribution(current, "Current", min_samples=1)

    # Identical distributions have zero PSI
    if ref_arr.shape == curr_arr.shape and np.array_equal(ref_arr, curr_arr):
        return 0.0

    # Define bin edges using reference distribution quantiles
    quantiles = np.linspace(0.0, 1.0, num_bins + 1)
    bins = np.quantile(ref_arr, quantiles)
    unique_bins = np.unique(bins)

    # If all reference values are identical, establish an interval around the value
    if len(unique_bins) < 2:
        val = unique_bins[0]
        unique_bins = np.array([val - 1.0, val + 1.0])

    # Extend edge bounds slightly to capture minimum and maximum observations inclusively
    unique_bins[0] = -np.inf
    unique_bins[-1] = np.inf

    # Bin frequencies
    ref_counts, _ = np.histogram(ref_arr, bins=unique_bins)
    curr_counts, _ = np.histogram(curr_arr, bins=unique_bins)

    # Convert to proportions with smoothing epsilon
    ref_proportions = (ref_counts + epsilon) / (len(ref_arr) + epsilon * len(ref_counts))
    curr_proportions = (curr_counts + epsilon) / (len(curr_arr) + epsilon * len(curr_counts))

    # Calculate PSI sum
    psi_terms = (curr_proportions - ref_proportions) * np.log(
        curr_proportions / ref_proportions
    )
    return float(np.sum(psi_terms))


def kolmogorov_smirnov(
    reference: Sequence[float] | np.ndarray,
    current: Sequence[float] | np.ndarray,
) -> tuple[float, float]:
    """Calculate the two-sample Kolmogorov-Smirnov statistic and asymptotic p-value.

    Returns:
        tuple[float, float]: (ks_statistic, p_value).
    """
    ref_arr = validate_distribution(reference, "Reference", min_samples=1)
    curr_arr = validate_distribution(current, "Current", min_samples=1)

    if ref_arr.shape == curr_arr.shape and np.array_equal(ref_arr, curr_arr):
        return 0.0, 1.0

    result = stats.ks_2samp(ref_arr, curr_arr)
    return float(result.statistic), float(result.pvalue)


def wasserstein_distance(
    reference: Sequence[float] | np.ndarray,
    current: Sequence[float] | np.ndarray,
) -> float:
    """Calculate the first Wasserstein distance (Earth Mover's Distance).

    Returns:
        float: Deterministic Wasserstein distance.
    """
    ref_arr = validate_distribution(reference, "Reference", min_samples=1)
    curr_arr = validate_distribution(current, "Current", min_samples=1)

    if ref_arr.shape == curr_arr.shape and np.array_equal(ref_arr, curr_arr):
        return 0.0

    return float(stats.wasserstein_distance(ref_arr, curr_arr))


def standardized_mean_shift(
    reference: Sequence[float] | np.ndarray,
    current: Sequence[float] | np.ndarray,
) -> float:
    """Calculate the absolute difference in means standardized by reference standard deviation.

    Shift = |mean(current) - mean(reference)| / std(reference)
    If std(reference) == 0, returns the raw absolute mean difference.

    Returns:
        float: Standardized mean shift.
    """
    ref_arr = validate_distribution(reference, "Reference", min_samples=1)
    curr_arr = validate_distribution(current, "Current", min_samples=1)

    ref_mean = float(np.mean(ref_arr))
    curr_mean = float(np.mean(curr_arr))
    ref_std = float(np.std(ref_arr))

    mean_diff = abs(curr_mean - ref_mean)
    if ref_std > 0.0:
        return float(mean_diff / ref_std)
    return float(mean_diff)
