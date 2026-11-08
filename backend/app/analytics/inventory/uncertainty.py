"""Forecast uncertainty propagation (Phase 5).

Consumes Phase 4 intervals; never computes new ones. Reports exposure
under point, lower-demand, and upper-demand cases with precise
terminology (never "worst-case guarantee").
"""

from backend.app.analytics.inventory.types import ForecastInput


def uncertainty_note(forecast: ForecastInput | None) -> str:
    """Describe inventory exposure across the interval cases."""
    if forecast is None or forecast.missing or not forecast.point:
        return "Forecast uncertainty is unknown: no forecast available."
    widths = [hi - lo for hi, lo in zip(forecast.upper, forecast.lower)]
    mean_width = sum(widths) / len(widths)
    mean_point = sum(forecast.point) / len(forecast.point)
    spread = (mean_width / mean_point) if mean_point > 0 else 0.0
    return (
        f"Upper forecast-bound scenario demand totals {sum(forecast.upper):.0f} "
        f"vs point {sum(forecast.point):.0f} and lower-bound {sum(forecast.lower):.0f} "
        f"over {forecast.horizon} days (level {forecast.confidence_level}). "
        f"Mean interval width {mean_width:.1f} (spread {spread:.2f} of mean demand). "
        "Coverage under upper demand is lowest; coverage under lower demand is highest."
    )
