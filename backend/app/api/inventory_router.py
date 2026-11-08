"""Inventory endpoints (Phase 12A): KPI overview, positions, health.

Read-only, org-scoped views over the Phase 3 KPI engines and the Phase 5
position/health rules. Series scans are bounded (500 keys) and paginated;
health rows with no forecast input surface UNKNOWN with explicit missing
evidence instead of a fabricated state.
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


def _overview_kpis(frames) -> dict:
    """Inventory KPI families plus the service family (threadpool-safe)."""
    families = support.build_inventory_kpis(frames)
    families["service"] = support.build_service_kpis(frames)
    return families


@router.get("/inventory/overview")
async def read_inventory_overview(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
) -> dict:
    """Inventory and service KPI families at one analysis date."""
    async with support.map_value_errors():
        context = await support.load_request_context(session, auth, analysis_date=analysis_date)
        families = await run_in_threadpool(_overview_kpis, context.frames)
    date_text = context.analysis_date.isoformat()
    return success_envelope(
        {
            "analysis_date": date_text,
            "kpis": families,
            "limitations": [
                "KPI rows are derived from synthetic snapshots and "
                "transactions (data_source_label=synthetic), capped at 100 "
                "rows per family.",
                "Days-of-supply requires a positive average daily demand; "
                "the family is empty otherwise.",
            ],
        },
        {
            "data_source_label": "synthetic",
            "source": "phase3_kpis",
            "analysis_date": date_text,
        },
    )


@router.get("/inventory/positions")
async def read_inventory_positions(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    product_id: str | None = Query(None, max_length=36),
    warehouse_id: str | None = Query(None, max_length=36),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
    paging: tuple[int, int] = Depends(support.pagination_params),
) -> dict:
    """Paginated point-in-time inventory positions per series."""
    page, page_size = paging
    async with support.map_value_errors():
        context = await support.load_request_context(
            session,
            auth,
            product_id=product_id,
            warehouse_id=warehouse_id,
            analysis_date=analysis_date,
        )
        keys = await run_in_threadpool(
            ctx.series_keys,
            context.frames,
            context.analysis_date,
            product_id,
            warehouse_id,
            support.MAX_API_SERIES,
        )
        positions = await run_in_threadpool(
            support.positions_for_keys, context.frames, keys, context.analysis_date
        )
    window = support.paginate(positions, page, page_size)
    date_text = context.analysis_date.isoformat()
    limitations = [
        "Positions use the latest snapshot on or before the analysis date.",
        f"Series scan bounded to the first {support.MAX_API_SERIES} keys in deterministic order.",
    ]
    if len(keys) >= support.MAX_API_SERIES:
        limitations.append(
            "The series bound was reached; additional series exist beyond this page set."
        )
    return success_envelope(
        {**window, "analysis_date": date_text},
        {
            "data_source_label": "synthetic",
            "source": "phase5_inventory_position",
            "analysis_date": date_text,
            "limitations": limitations,
        },
    )


@router.get("/inventory/health")
async def read_inventory_health(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    product_id: str | None = Query(None, max_length=36),
    warehouse_id: str | None = Query(None, max_length=36),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
    paging: tuple[int, int] = Depends(support.pagination_params),
) -> dict:
    """Paginated rule-based inventory health classifications."""
    page, page_size = paging
    async with support.map_value_errors():
        context = await support.load_request_context(
            session,
            auth,
            product_id=product_id,
            warehouse_id=warehouse_id,
            analysis_date=analysis_date,
        )
        keys = await run_in_threadpool(
            ctx.series_keys,
            context.frames,
            context.analysis_date,
            product_id,
            warehouse_id,
            support.MAX_API_SERIES,
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
            support.health_for_keys,
            context.frames,
            keys,
            forecasts,
            context.analysis_date,
        )
    window = support.paginate(rows, page, page_size)
    date_text = context.analysis_date.isoformat()
    limitations = [
        "Health states are rule-based classifications over positions and "
        "forecasts (Phase 5 thresholds), never predictions.",
        f"Forecast inputs follow the persisted-first adapter (first "
        f"{ctx.MAX_SERIES} series); series beyond that bound surface "
        "UNKNOWN with missing evidence.",
    ]
    if not rows:
        limitations.append("No inventory series matched the request.")
    return success_envelope(
        {**window, "analysis_date": date_text},
        {
            "data_source_label": "synthetic",
            "source": "phase5_inventory_health",
            "analysis_date": date_text,
            "limitations": limitations,
        },
    )


__all__ = ["router"]
