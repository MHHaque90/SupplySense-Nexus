"""Targeted unit and integration tests for Model Drift Monitoring and Registry (Phase 13C)."""

import numpy as np
import pytest

from backend.app.analytics.drift import (
    DriftEvaluator,
    DriftStatus,
    ModelRegistry,
    ModelStatus,
    kolmogorov_smirnov,
    population_stability_index,
    standardized_mean_shift,
    validate_distribution,
    wasserstein_distance,
)
from backend.app.core.data_labels import DataSourceLabel


@pytest.fixture
def baseline_distribution() -> list[float]:
    """Synthetic baseline demand distribution with known seed."""
    rng = np.random.default_rng(42)
    return [float(x) for x in rng.normal(loc=100.0, scale=15.0, size=150)]


@pytest.fixture
def shifted_distribution() -> list[float]:
    """Synthetic shifted distribution representing demand surge and variance increase."""
    rng = np.random.default_rng(99)
    return [float(x) for x in rng.normal(loc=160.0, scale=30.0, size=150)]


def test_identical_distributions_no_drift(baseline_distribution: list[float]):
    """Identical distributions must result in zero divergence and NO_DRIFT status."""
    psi = population_stability_index(baseline_distribution, baseline_distribution)
    assert psi == 0.0

    ks_stat, p_val = kolmogorov_smirnov(baseline_distribution, baseline_distribution)
    assert ks_stat == 0.0
    assert p_val == 1.0

    wd = wasserstein_distance(baseline_distribution, baseline_distribution)
    assert wd == 0.0

    ms = standardized_mean_shift(baseline_distribution, baseline_distribution)
    assert ms == 0.0

    evaluator = DriftEvaluator()
    result = evaluator.evaluate(
        reference=baseline_distribution,
        current=baseline_distribution,
        metric="psi",
        model_id="test_model",
        model_version="1.0.0",
    )
    assert result.status == DriftStatus.NO_DRIFT
    assert result.metric_value == 0.0
    assert result.threshold == 0.20


def test_distribution_shift_detected(
    baseline_distribution: list[float], shifted_distribution: list[float]
):
    """Substantial distribution shift must trigger DRIFT_DETECTED status."""
    evaluator = DriftEvaluator()

    # Test PSI
    psi_result = evaluator.evaluate(
        reference=baseline_distribution,
        current=shifted_distribution,
        metric="psi",
        model_id="hgb",
        model_version="4.0.0",
    )
    assert psi_result.status == DriftStatus.DRIFT_DETECTED
    assert psi_result.metric_value is not None
    assert psi_result.metric_value >= 0.20

    # Test KS test
    ks_result = evaluator.evaluate(
        reference=baseline_distribution,
        current=shifted_distribution,
        metric="ks",
        model_id="hgb",
        model_version="4.0.0",
    )
    assert ks_result.status == DriftStatus.DRIFT_DETECTED
    assert ks_result.p_value is not None
    assert ks_result.p_value <= 0.05

    # Test Wasserstein distance
    wd_result = evaluator.evaluate(
        reference=baseline_distribution,
        current=shifted_distribution,
        metric="wasserstein",
        threshold=10.0,
        model_id="hgb",
        model_version="4.0.0",
    )
    assert wd_result.status == DriftStatus.DRIFT_DETECTED
    assert wd_result.metric_value is not None
    assert wd_result.metric_value > 10.0


def test_insufficient_or_empty_data(baseline_distribution: list[float]):
    """Fewer samples than min_samples or empty inputs must produce INSUFFICIENT_DATA."""
    evaluator = DriftEvaluator(min_samples=5)

    # Empty inputs
    res_empty = evaluator.evaluate(
        reference=[],
        current=[10.0, 11.0, 12.0, 13.0, 14.0],
        metric="psi",
    )
    assert res_empty.status == DriftStatus.INSUFFICIENT_DATA
    assert res_empty.metric_value is None
    assert res_empty.reference_count == 0

    # Below min_samples
    res_small = evaluator.evaluate(
        reference=baseline_distribution,
        current=[100.0, 102.0],  # only 2 samples < 5
        metric="psi",
    )
    assert res_small.status == DriftStatus.INSUFFICIENT_DATA
    assert res_small.metric_value is None
    assert res_small.current_count == 2


def test_invalid_inputs_handled_safely(baseline_distribution: list[float]):
    """Non-finite inputs (NaN, Inf) must be safely intercepted without crashing."""
    evaluator = DriftEvaluator()
    bad_current = [100.0, float("nan"), 105.0, 108.0, 110.0, float("inf")]

    # Evaluator catches errors and returns INSUFFICIENT_DATA with audit error context
    result = evaluator.evaluate(
        reference=baseline_distribution,
        current=bad_current,
        metric="psi",
    )
    assert result.status == DriftStatus.INSUFFICIENT_DATA
    assert result.metric_value is None
    assert "error" in result.context

    # Direct validation raises clear ValueError
    with pytest.raises(ValueError, match="non-finite"):
        validate_distribution(bad_current, "Test")


def test_deterministic_evaluation(
    baseline_distribution: list[float], shifted_distribution: list[float]
):
    """Repeated evaluations of identical inputs must yield bit-exact results."""
    evaluator = DriftEvaluator()

    runs = [
        evaluator.evaluate(
            reference=baseline_distribution,
            current=shifted_distribution,
            metric="psi",
            model_id="test_model",
            model_version="4.0.0",
        )
        for _ in range(5)
    ]

    first_val = runs[0].metric_value
    first_status = runs[0].status
    assert all(r.metric_value == first_val for r in runs)
    assert all(r.status == first_status for r in runs)


def test_threshold_behavior(baseline_distribution: list[float]):
    """Threshold changes must deterministically alter status between DRIFT and NO_DRIFT."""
    evaluator = DriftEvaluator()
    # Mild shift
    rng = np.random.default_rng(7)
    mild_shift = [float(x) for x in rng.normal(loc=104.0, scale=15.0, size=150)]

    # Lenient threshold: NO_DRIFT
    lenient = evaluator.evaluate(
        reference=baseline_distribution,
        current=mild_shift,
        metric="psi",
        threshold=0.50,
    )
    assert lenient.status == DriftStatus.NO_DRIFT
    assert lenient.threshold == 0.50

    # Very strict threshold: DRIFT_DETECTED
    strict = evaluator.evaluate(
        reference=baseline_distribution,
        current=mild_shift,
        metric="psi",
        threshold=0.001,
    )
    assert strict.status == DriftStatus.DRIFT_DETECTED
    assert strict.threshold == 0.001


def test_model_traceability_and_provenance(baseline_distribution: list[float]):
    """Evaluation result must capture model identity, version, metric, context, and label."""
    evaluator = DriftEvaluator()
    context = {"series_id": "SKU-001:WH-01", "horizon": 30, "feature": "inbound_leadtime"}

    result = evaluator.evaluate(
        reference=baseline_distribution,
        current=baseline_distribution,
        metric="mean_shift",
        threshold=1.5,
        model_id="holt_winters",
        model_version="4.0.0",
        context=context,
        data_source_label=DataSourceLabel.DERIVED.value,
    )

    assert result.model_id == "holt_winters"
    assert result.model_version == "4.0.0"
    assert result.metric == "mean_shift"
    assert result.threshold == 1.5
    assert result.context["series_id"] == "SKU-001:WH-01"
    assert result.data_source_label == DataSourceLabel.DERIVED.value
    assert isinstance(result.evaluated_at, str) and len(result.evaluated_at) > 0

    # Serialization test
    d = result.to_dict()
    assert d["status"] == DriftStatus.NO_DRIFT.value
    assert d["model_id"] == "holt_winters"
    assert d["context"]["horizon"] == 30


def test_model_registry_lifecycle():
    """ModelRegistry must support seeding, version creation, status promotion, and history."""
    registry = ModelRegistry(auto_seed=True)

    # 1. Verify seeded Phase 4 models
    active_hgb = registry.get_active_version("hgb")
    assert active_hgb is not None
    assert active_hgb.version == "4.0.0"
    assert active_hgb.status == ModelStatus.ACTIVE
    assert active_hgb.model_type == "ml"

    # 2. Register candidate version 4.1.0
    v41 = registry.create_version(
        model_name="hgb",
        version="4.1.0",
        model_type="ml",
        status=ModelStatus.CANDIDATE,
        features=["history", "promotions", "lead_time"],
        metrics={"mae": 4.12, "rmse": 6.85},
        reference_distribution=[10.0, 20.0, 30.0],
    )
    assert v41.model_id == "hgb:4.1.0"
    assert v41.status == ModelStatus.CANDIDATE
    # Active version is still 4.0.0
    assert registry.get_active_version("hgb").version == "4.0.0"

    # 3. Promote 4.1.0 to active
    promoted = registry.set_active_version("hgb", "4.1.0")
    assert promoted.status == ModelStatus.ACTIVE
    assert registry.get_active_version("hgb").version == "4.1.0"

    # Old version must now be ARCHIVED
    old_version = registry.get_version("hgb", "4.0.0")
    assert old_version is not None
    assert old_version.status == ModelStatus.ARCHIVED

    # 4. Record drift evaluation in registry
    evaluator = DriftEvaluator()
    drift_res = evaluator.evaluate(
        reference=[10.0, 20.0, 30.0, 40.0, 50.0],
        current=[10.0, 20.0, 30.0, 40.0, 50.0],
        model_id="hgb:4.1.0",
        model_version="4.1.0",
    )
    registry.record_drift(drift_res)

    history = registry.get_drift_history(model_id="hgb:4.1.0")
    assert len(history) == 1
    assert history[0].model_id == "hgb:4.1.0"
    assert history[0].status == DriftStatus.NO_DRIFT
