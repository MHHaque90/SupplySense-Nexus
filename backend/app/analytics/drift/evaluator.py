"""Deterministic drift evaluator for model prediction and feature monitoring."""

from collections.abc import Sequence
from typing import Any

from backend.app.analytics.drift.metrics import (
    kolmogorov_smirnov,
    population_stability_index,
    standardized_mean_shift,
    wasserstein_distance,
)
from backend.app.analytics.drift.types import DriftEvaluationResult, DriftStatus
from backend.app.core.data_labels import DataSourceLabel

DEFAULT_THRESHOLDS: dict[str, float] = {
    "psi": 0.20,
    "ks": 0.05,  # p-value threshold: p <= 0.05 flags statistically significant divergence
    "wasserstein": 1.0,
    "mean_shift": 1.5,
}

DEFAULT_MIN_SAMPLES: int = 5


class DriftEvaluator:
    """Evaluates distribution drift against deterministic thresholds.

    Calculates numeric drift metrics and produces auditable, machine-readable
    status indicators without advisory language or optimization.
    """

    def __init__(
        self,
        thresholds: dict[str, float] | None = None,
        min_samples: int = DEFAULT_MIN_SAMPLES,
    ) -> None:
        """Initialize with custom or default thresholds and sample bounds."""
        self.thresholds = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self.thresholds.update(thresholds)
        self.min_samples = max(1, min_samples)

    def evaluate(
        self,
        reference: Sequence[float],
        current: Sequence[float],
        metric: str = "psi",
        threshold: float | None = None,
        model_id: str = "unspecified",
        model_version: str = "unspecified",
        context: dict[str, Any] | None = None,
        data_source_label: str = DataSourceLabel.DERIVED.value,
    ) -> DriftEvaluationResult:
        """Evaluate drift between reference and current distributions deterministically.

        Parameters:
            reference: Baseline distribution observations.
            current: Target/evaluation distribution observations.
            metric: Drift metric to compute ('psi', 'ks', 'wasserstein', 'mean_shift').
            threshold: Explicit threshold override. If None, uses configured threshold.
            model_id: Identifier of model associated with this distribution.
            model_version: Version of the evaluated model.
            context: Additional audit context (e.g. series_id, feature_name, date_range).
            data_source_label: Data provenance label (default: 'derived').

        Returns:
            DriftEvaluationResult with machine-readable status and numeric metrics.
        """
        metric_key = metric.lower().strip()
        eff_threshold = threshold if threshold is not None else self.thresholds.get(metric_key, 0.20)
        eval_context = dict(context or {})

        ref_len = len(reference) if reference is not None else 0
        curr_len = len(current) if current is not None else 0

        # Insufficient data check
        if ref_len < self.min_samples or curr_len < self.min_samples:
            return DriftEvaluationResult(
                model_id=model_id,
                model_version=model_version,
                metric=metric_key,
                metric_value=None,
                threshold=eff_threshold,
                status=DriftStatus.INSUFFICIENT_DATA,
                reference_count=ref_len,
                current_count=curr_len,
                context=eval_context,
                data_source_label=data_source_label,
            )

        try:
            if metric_key == "psi":
                val = population_stability_index(reference, current)
                is_drift = val >= eff_threshold
                p_val = None
            elif metric_key == "ks":
                stat, p_val = kolmogorov_smirnov(reference, current)
                val = stat
                # For KS, p-value below threshold indicates distribution mismatch
                is_drift = p_val <= eff_threshold
            elif metric_key == "wasserstein":
                val = wasserstein_distance(reference, current)
                is_drift = val >= eff_threshold
                p_val = None
            elif metric_key == "mean_shift":
                val = standardized_mean_shift(reference, current)
                is_drift = val >= eff_threshold
                p_val = None
            else:
                raise ValueError(
                    f"Unsupported drift metric '{metric}'. Supported metrics: "
                    f"{sorted(self.thresholds.keys())}."
                )

            status = DriftStatus.DRIFT_DETECTED if is_drift else DriftStatus.NO_DRIFT

            return DriftEvaluationResult(
                model_id=model_id,
                model_version=model_version,
                metric=metric_key,
                metric_value=float(val),
                threshold=float(eff_threshold),
                status=status,
                reference_count=ref_len,
                current_count=curr_len,
                context=eval_context,
                p_value=p_val,
                data_source_label=data_source_label,
            )
        except Exception as exc:
            # Handle non-finite or computation errors cleanly
            eval_context["error"] = str(exc)
            return DriftEvaluationResult(
                model_id=model_id,
                model_version=model_version,
                metric=metric_key,
                metric_value=None,
                threshold=eff_threshold,
                status=DriftStatus.INSUFFICIENT_DATA,
                reference_count=ref_len,
                current_count=curr_len,
                context=eval_context,
                data_source_label=data_source_label,
            )
