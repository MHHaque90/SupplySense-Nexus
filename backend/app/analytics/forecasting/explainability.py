"""Lightweight forecast explainability (Phase 4).

Templated, evidence-backed reasons only — no causal claims, no SHAP,
no extra dependencies. Confidence is a structured descriptor with
supporting evidence, explicitly not a probability of correctness.
"""

from backend.app.analytics.types import ModelComparison, SeriesProfile

_MODEL_REASONS: dict[str, str] = {
    "zero": "All-zero history produces a deterministic zero forecast.",
    "naive": "Naive selected because recent-level repetition produced the lowest validation error.",
    "seasonal_naive": "Seasonal Naive selected because the seasonal cycle produced the lowest validation error.",
    "moving_average": "Moving Average selected because trailing-level smoothing produced the lowest validation error.",
    "drift": "Drift selected because sustained trend extrapolation produced the lowest validation error.",
    "ses": "SES selected because smoothed-level estimation produced the lowest validation error.",
    "holt": "Holt selected because the series showed sustained trend and outperformed baseline models.",
    "holt_winters": "Holt-Winters selected because seasonal structure produced the lowest validation error.",
    "autoreg": "Autoregressive selected because lag structure produced the lowest validation error.",
    "croston": "Croston selected because intermittent-demand rate estimation produced the lowest validation error.",
    "hgb": "Gradient boosting selected because leakage-safe history features produced the lowest validation error.",
    "ensemble_average": "Equal-weight ensemble selected because averaging members produced the lowest validation error.",
    "ensemble_weighted": "Inverse-error ensemble selected because error-weighted averaging produced the lowest validation error.",
}


def explain_selection(
    model_name: str,
    profile: SeriesProfile,
    comparison: ModelComparison,
) -> str:
    """Build a human-readable selection reason from validation evidence."""
    base = _MODEL_REASONS.get(model_name, f"{model_name} produced the lowest validation error.")
    score = comparison.scores.get(model_name)
    score_text = f" {comparison.metric}={score:.3f}" if score is not None else ""
    return (
        f"{base} Observed series profile is '{profile.profile}' "
        f"({profile.observations} observations, mean {profile.mean_demand:.2f}).{score_text}"
    )


def fallback_explanation(reason: str, fallback_model: str) -> str:
    """Explain why a fallback model was used."""
    return f"{fallback_model} fallback used because {reason}"


def insufficient_history_explanation(required: int, available: int) -> str:
    """Explain an insufficient-history outcome."""
    return (
        f"Insufficient history: {available} observations available, "
        f"{required} required for validation. No forecast produced."
    )


def confidence_descriptor(
    folds: int,
    error: float | None,
    volatility: float | None,
    zero_ratio: float,
) -> dict[str, object]:
    """Describe validation support as strong/moderate/limited/insufficient.

    This is an analytical confidence descriptor, not a probability of
    correctness.
    """
    evidence = {
        "folds": folds,
        "validation_error": error,
        "volatility": volatility,
        "zero_ratio": zero_ratio,
    }
    if folds < 1 or error is None:
        return {"level": "insufficient evidence", "evidence": evidence}
    if folds >= 5 and error < 0.2 and (volatility or 0.0) < 0.8 and zero_ratio < 0.2:
        level = "strong validation support"
    elif folds >= 3 and error < 0.4:
        level = "moderate validation support"
    else:
        level = "limited validation support"
    return {"level": level, "evidence": evidence}
