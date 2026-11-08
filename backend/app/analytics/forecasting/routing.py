"""Demand-profile-aware model routing (Phase 4).

Routing uses OBSERVED demand statistics (Phase 3 ``SeriesProfile``),
never the generator's source metadata. Each profile maps to a small
candidate set; history gates remove unsupported models up front.
"""

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.features.profiles import profile_series
from backend.app.analytics.forecasting.decomposition import detect_seasonality
from backend.app.analytics.types import SeriesProfile

_PROFILE_CANDIDATES: dict[str, list[str]] = {
    "zero": ["zero"],
    "constant": ["naive", "moving_average", "ses"],
    "intermittent": ["croston", "moving_average", "naive"],
    "stable": ["naive", "moving_average", "ses", "holt"],
    "trending": ["drift", "holt", "autoreg", "moving_average"],
    "volatile": ["moving_average", "ses", "naive", "holt"],
    "seasonal": ["seasonal_naive", "holt_winters", "holt", "moving_average"],
}

# Minimum observations each model needs to be attempted.
_MODEL_MINIMUMS: dict[str, int] = {
    "zero": 1,
    "naive": 1,
    "moving_average": 7,
    "ses": 1,
    "drift": 2,
    "holt": 4,
    "croston": 2,
    "seasonal_naive": 7,
    "holt_winters": 14,
    "autoreg": 18,
    "hgb": 90,
}


def route_series(
    values: list[float],
    config: AnalyticsConfig | None = None,
    season: int = 7,
    include_ml: bool = False,
    dates: object | None = None,
) -> tuple[SeriesProfile, list[str], list[str]]:
    """Route one series to candidate models.

    Returns ``(profile, candidates, reasons)`` where reasons explains
    each inclusion or exclusion in the same order as candidates plus
    trailing exclusion notes.
    """
    profile = profile_series(values)
    candidates = list(_PROFILE_CANDIDATES.get(profile.profile, ["naive", "moving_average", "ses"]))
    reasons = [f"profile '{profile.profile}' routes to {name}" for name in candidates]
    # Seasonal augmentation for stable/volatile series with detected cycles.
    if profile.profile in ("stable", "volatile"):
        finding = detect_seasonality(values, dates, periods=(season,))
        if finding.period is not None:
            for name in ("seasonal_naive", "holt_winters"):
                if name not in candidates:
                    candidates.append(name)
                    reasons.append(
                        f"seasonal period {finding.period} detected "
                        f"(strength {finding.strength:.2f}); {name} added"
                    )
    # History gates.
    gated: list[str] = []
    for name in candidates:
        minimum = _MODEL_MINIMUMS.get(name, 1)
        if name == "seasonal_naive":
            minimum = season
        if name == "holt_winters":
            minimum = 2 * season
        if len(values) >= minimum:
            gated.append(name)
        else:
            reasons.append(
                f"{name} excluded: needs {minimum} observations, series has {len(values)}"
            )
    if not include_ml and "hgb" in gated:
        gated.remove("hgb")
        reasons.append("hgb excluded: ML candidates require explicit opt-in")
    if include_ml and profile.profile in ("stable", "volatile") and len(values) >= 90 and "hgb" not in gated:
        gated.append("hgb")
        reasons.append("hgb included: stable/volatile series with 90+ observations")
    if not gated:
        gated = ["naive"] if len(values) >= 1 else ["zero"]
        reasons.append("fallback: no candidate passed history gates")
    return profile, gated, reasons
