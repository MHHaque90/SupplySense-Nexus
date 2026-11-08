"""Analytics reporting (Phase 3).

Machine-readable JSON plus human-readable Markdown. Analytical wording
only: the synthetic dataset shows patterns; nothing here describes real
business performance.
"""

from backend.app.analytics.reports import (
    analytics_report,
    forecast_report,
    forecasting_report,
    inventory_report,
)

__all__ = ["analytics_report", "forecast_report", "forecasting_report", "inventory_report"]
