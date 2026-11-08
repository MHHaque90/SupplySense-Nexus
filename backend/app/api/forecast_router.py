"""Forecast endpoint (Phase 12A): Phase 4 forecast inputs for charts.

The response always carries ``data_source_label = "forecast"`` so the
frontend can render estimates as forecasts, never as actuals. Series
generation follows the persisted-first adapter (bounded to the first 25
series in deterministic order); the bound is declared in limitations.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.ai.tools import _context as ctx
from backend.app.api import analytics_support as support
from backend.app.api.analytics_support import ANALYST_PLUS
from backend.app.core.database import get_db
from backend.app.core.errors import success_envelope
from backend.app.core.security import AuthContext, require_roles

router = APIRouter()

_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


@router.get("/forecast")
async def read_forecast(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    product_id: str | None = Query(None, max_length=36),
    warehouse_id: str | None = Query(None, max_length=36),
    horizon: int | None = Query(None, ge=1, le=366),
    profile: str | None = Query(None, max_length=40),
    start_date: str | None = Query(None, pattern=_DATE_PATTERN),
    end_date: str | None = Query(None, pattern=_DATE_PATTERN),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
    paging: tuple[int, int] = Depends(support.pagination_params),
) -> dict:
    """Paginated forecast series with point and interval values."""
    page, page_size = paging
    async with support.map_value_errors():
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must not be after end_date.")
        context = await support.load_request_context(
            session,
            auth,
            product_id=product_id,
            warehouse_id=warehouse_id,
            analysis_date=analysis_date,
        )
        forecasts = await ctx.build_forecasts(
            session,
            context.frames,
            context.scope,
            context.analysis_date,
            product_id,
            warehouse_id,
        )
        rows = await run_in_threadpool(
            support.forecast_rows,
            forecasts,
            horizon=horizon,
            profile=profile,
            start_date=start_date,
            end_date=end_date,
        )
    window = support.paginate(rows, page, page_size)
    date_text = context.analysis_date.isoformat()
    limitations = [
        "Forecast values are estimates with uncertainty intervals, not "
        "observed actuals (data_source_label=forecast).",
        f"Series follow the persisted-first adapter, bounded to the first "
        f"{ctx.MAX_SERIES} series in deterministic order.",
    ]
    if horizon is not None:
        limitations.append(
            f"Requested horizon {horizon} day(s) applied per series after date filtering."
        )
    if not rows:
        limitations.append("No forecast series matched the request.")
    return success_envelope(
        {**window, "analysis_date": date_text},
        {
            "data_source_label": "forecast",
            "source": "phase4_forecasting",
            "analysis_date": date_text,
            "limitations": limitations,
        },
    )


__all__ = ["router"]
