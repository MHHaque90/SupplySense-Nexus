"""Risk register endpoint (Phase 12A): Phase 7 records with filters.

Composes the Phase 5 → 6 → 7 pipeline once per request and paginates the
filtered register. The overview counts always describe the FULL register
for the analysis date; ``items`` honors the query filters. Sev/counts are
deterministic rules over synthetic data — never predictions.
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


def _register_records(frames, forecasts, analysis_date, horizon_days: int) -> list:
    """Run the Phase 5→6→7 pipeline once (threadpool-safe composition)."""
    intelligence = support.build_intelligence(frames, forecasts, analysis_date)
    supplier_results = support.build_supplier_results(frames, intelligence, analysis_date)
    return support.build_risk_records(
        frames, intelligence, supplier_results, analysis_date, horizon_days
    )


@router.get("/risk")
async def read_risk(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    severity: str | None = Query(None, max_length=32),
    domain: str | None = Query(None, max_length=40),
    supplier_id: str | None = Query(None, max_length=36),
    product_id: str | None = Query(None, max_length=36),
    warehouse_id: str | None = Query(None, max_length=36),
    horizon_days: int = Query(28, ge=1, le=180),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
    paging: tuple[int, int] = Depends(support.pagination_params),
) -> dict:
    """Paginated risk register rows plus the full-register overview."""
    page, page_size = paging
    async with support.map_value_errors():
        context = await support.load_request_context(
            session,
            auth,
            product_id=product_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier_id,
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
        records = await run_in_threadpool(
            _register_records,
            context.frames,
            forecasts,
            context.analysis_date,
            horizon_days,
        )
        filtered = support.filter_risk_records(
            records,
            severity=severity,
            domain=domain,
            supplier_id=supplier_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            include_unknown=True,
        )
        report = support.build_risk_report(records, context.analysis_date, horizon_days)
        items = [record.to_dict() for record in filtered]
    window = support.paginate(items, page, page_size)
    date_text = context.analysis_date.isoformat()
    limitations = list(report.get("limitations") or [])
    limitations.append(
        "Overview counts describe the full register for the analysis date; "
        "items honor the query filters."
    )
    if severity or domain or supplier_id or product_id or warehouse_id:
        if not filtered:
            limitations.append("No register rows matched the requested filters.")
    return success_envelope(
        {
            **window,
            "analysis_date": date_text,
            "horizon_days": horizon_days,
            "overview": report["risk_overview"],
            "limitations": limitations,
        },
        {
            "data_source_label": "synthetic",
            "source": "phase7_risk_register",
            "analysis_date": date_text,
        },
    )


__all__ = ["router"]
