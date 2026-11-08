"""Executive dashboard summary endpoint (Phase 12A).

One org-scoped read composing the Phase 3 KPI families with the Phase 7
risk overview so the dashboard renders without N round trips. Everything
is derived from the synthetic organization dataset; forecast-dependent
risk records are absent when no forecast inputs exist (stated in
limitations, never fabricated).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.ai.tools import _context as ctx
from backend.app.analytics.forecasting import persistence as forecast_persistence
from backend.app.api import analytics_support as support
from backend.app.api.analytics_support import ANALYST_PLUS
from backend.app.core.database import get_db
from backend.app.core.errors import success_envelope
from backend.app.core.security import AuthContext, require_roles

router = APIRouter()

_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def _summary(frames, forecasts, analysis_date, horizon_days: int) -> dict:
    """Compose KPI families plus the risk overview (threadpool-safe)."""
    intelligence = support.build_intelligence(frames, forecasts, analysis_date)
    supplier_results = support.build_supplier_results(frames, intelligence, analysis_date)
    records = support.build_risk_records(
        frames, intelligence, supplier_results, analysis_date, horizon_days
    )
    report = support.build_risk_report(records, analysis_date, horizon_days)
    families = {
        "demand": support.build_demand_kpis(frames),
        "inventory": support.build_inventory_kpis(frames),
        "service": support.build_service_kpis(frames),
        "procurement": support.build_procurement_kpis(frames),
    }
    return {"kpis": families, "risk": report["risk_overview"]}


@router.get("/dashboard/overview")
async def read_dashboard_overview(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
    horizon_days: int = Query(28, ge=1, le=180),
) -> dict:
    """KPI families, risk overview, and forecast status for one date."""
    async with support.map_value_errors():
        context = await support.load_request_context(session, auth, analysis_date=analysis_date)
        forecasts = await ctx.build_forecasts(
            session, context.frames, context.scope, context.analysis_date
        )
        summary = await run_in_threadpool(
            _summary,
            context.frames,
            forecasts,
            context.analysis_date,
            horizon_days,
        )
        persisted_rows = await forecast_persistence.forecast_row_count(session)
    date_text = context.analysis_date.isoformat()
    limitations = [
        "KPI rows are derived from the synthetic organization dataset "
        "(data_source_label=derived) and are capped at 100 rows per family.",
        "Risk severity counts are deterministic rules over synthetic data, not predictions.",
        f"Persisted Phase 4 forecast rows in this deployment: {persisted_rows}.",
    ]
    if not forecasts:
        limitations.append(
            "No forecast inputs were available for this organization; "
            "forecast-dependent risk records are absent."
        )
    return success_envelope(
        {
            "analysis_date": date_text,
            "horizon_days": horizon_days,
            "kpis": summary["kpis"],
            "risk": summary["risk"],
            "forecast_status": {"persisted_forecast_rows": persisted_rows},
            "limitations": limitations,
        },
        {
            "data_source_label": "derived",
            "source": "phase3_phase7_analytics",
            "analysis_date": date_text,
        },
    )


__all__ = ["router"]
