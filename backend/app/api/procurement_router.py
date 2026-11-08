"""Procurement endpoints (Phase 12A): KPIs, open orders, inbound, risk.

Descriptive Phase 6 intelligence exposed read-only: no planning, no
ordering, no supplier recommendations. Open-order rows describe
outstanding PO lines; inbound coverage states keep unknowns explicit.
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


@router.get("/procurement/overview")
async def read_procurement_overview(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
) -> dict:
    """Procurement KPI families at one analysis date."""
    async with support.map_value_errors():
        context = await support.load_request_context(session, auth, analysis_date=analysis_date)
        families = await run_in_threadpool(support.build_procurement_kpis, context.frames)
    date_text = context.analysis_date.isoformat()
    return success_envelope(
        {
            "analysis_date": date_text,
            "kpis": families,
            "limitations": [
                "KPI rows are derived from synthetic purchase orders and "
                "shipments (data_source_label=synthetic), capped at 100 "
                "rows per family.",
                "Concentration is an exposure metric, never a diversification order or ranking.",
            ],
        },
        {
            "data_source_label": "synthetic",
            "source": "phase3_kpis",
            "analysis_date": date_text,
        },
    )


@router.get("/procurement/open-orders")
async def read_open_orders(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    supplier_id: str | None = Query(None, max_length=36),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
    paging: tuple[int, int] = Depends(support.pagination_params),
) -> dict:
    """Paginated open purchase-order lines at the analysis date."""
    page, page_size = paging
    async with support.map_value_errors():
        context = await support.load_request_context(
            session, auth, supplier_id=supplier_id, analysis_date=analysis_date
        )
        rows = await run_in_threadpool(
            support.open_order_rows,
            context.frames,
            context.analysis_date,
            [supplier_id] if supplier_id else None,
        )
    window = support.paginate(rows, page, page_size)
    date_text = context.analysis_date.isoformat()
    return success_envelope(
        {**window, "analysis_date": date_text},
        {
            "data_source_label": "synthetic",
            "source": "phase6_open_orders",
            "analysis_date": date_text,
            "limitations": [
                "Open = ordered or partially_received at the analysis date; "
                "received quantity is inferred from delivered shipments "
                "linked to the PO.",
                "Rows describe outstanding work — never a prioritized work queue.",
            ],
        },
    )


@router.get("/procurement/inbound")
async def read_inbound_coverage(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    product_id: str | None = Query(None, max_length=36),
    warehouse_id: str | None = Query(None, max_length=36),
    horizon_days: int = Query(28, ge=1, le=180),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
    paging: tuple[int, int] = Depends(support.pagination_params),
) -> dict:
    """Paginated inbound coverage states per series (unknowns explicit)."""
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
            support.inbound_coverage_rows,
            context.frames,
            keys,
            forecasts,
            context.analysis_date,
            horizon_days,
        )
    window = support.paginate(rows, page, page_size)
    date_text = context.analysis_date.isoformat()
    return success_envelope(
        {**window, "analysis_date": date_text, "horizon_days": horizon_days},
        {
            "data_source_label": "synthetic",
            "source": "phase6_inbound_coverage",
            "analysis_date": date_text,
            "limitations": [
                "Coverage states are descriptive (INBOUND_SUPPORTED, "
                "NO_KNOWN_INBOUND, INBOUND_INSUFFICIENT); arrival is never "
                "guaranteed.",
                "States are UNKNOWN without a forecast and an inventory position for the series.",
                "Known inbound counts open-order expected arrivals inside the horizon window only.",
            ],
        },
    )


@router.get("/procurement/risk")
async def read_procurement_risk(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    supplier_id: str | None = Query(None, max_length=36),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
    paging: tuple[int, int] = Depends(support.pagination_params),
) -> dict:
    """Paginated Phase 6 risk-signal rows per supplier (unranked)."""
    page, page_size = paging
    async with support.map_value_errors():
        context = await support.load_request_context(
            session, auth, supplier_id=supplier_id, analysis_date=analysis_date
        )
        forecasts = await ctx.build_forecasts(
            session, context.frames, context.scope, context.analysis_date
        )
        intelligence = await run_in_threadpool(
            support.build_intelligence,
            context.frames,
            forecasts,
            context.analysis_date,
        )
        signals = await run_in_threadpool(
            support.procurement_risk_signals,
            context.frames,
            intelligence,
            context.analysis_date,
            supplier_id,
        )
    window = support.paginate(signals, page, page_size)
    date_text = context.analysis_date.isoformat()
    return success_envelope(
        {**window, "analysis_date": date_text},
        {
            "data_source_label": "synthetic",
            "source": "phase6_risk_signals",
            "analysis_date": date_text,
            "limitations": [
                "Risk signals are descriptive categories over synthetic "
                "data — never rankings, probabilities, or recommendations.",
                "Rows are emitted in supplier-id order; absence of a signal "
                "means no evidence, not safety.",
            ],
        },
    )


__all__ = ["router"]
