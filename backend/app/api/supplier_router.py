"""Supplier endpoints (Phase 12A): directory and performance facts.

Descriptive only: supplier rows and Phase 6 performance metrics are never
ordered, scored, or labeled best/worst (Phase 11 C2 discipline carries
over — no recommendations, no rankings).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.api import analytics_support as support
from backend.app.api.analytics_support import ANALYST_PLUS
from backend.app.core.database import get_db
from backend.app.core.errors import success_envelope
from backend.app.core.security import AuthContext, require_roles

router = APIRouter()

_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


@router.get("/suppliers")
async def read_suppliers(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    paging: tuple[int, int] = Depends(support.pagination_params),
) -> dict:
    """Paginated org-scoped supplier directory (deduplicated links)."""
    page, page_size = paging
    async with support.map_value_errors():
        context = await support.load_request_context(session, auth)
        rows = await run_in_threadpool(support.unique_suppliers, context.frames.supplier_links)
    window = support.paginate(rows, page, page_size)
    return success_envelope(
        window,
        {
            "data_source_label": "synthetic",
            "source": "supplier_products",
            "limitations": [
                "Supplier rows are deduplicated supplier×product links from "
                "the synthetic dataset; rating values are synthetic labels.",
            ],
        },
    )


@router.get("/suppliers/performance")
async def read_supplier_performance(
    auth: AuthContext = Depends(require_roles(*ANALYST_PLUS)),
    session: AsyncSession = Depends(get_db),
    supplier_id: str | None = Query(None, max_length=36),
    analysis_date: str | None = Query(None, pattern=_DATE_PATTERN),
    paging: tuple[int, int] = Depends(support.pagination_params),
) -> dict:
    """Paginated descriptive performance facts per supplier (unranked)."""
    page, page_size = paging
    async with support.map_value_errors():
        context = await support.load_request_context(
            session, auth, supplier_id=supplier_id, analysis_date=analysis_date
        )
        if supplier_id:
            supplier_ids = [supplier_id]
        else:
            supplier_ids = (
                [
                    str(value)
                    for value in sorted(
                        context.frames.supplier_links["supplier_id"].astype(str).unique().tolist()
                    )
                ]
                if not context.frames.supplier_links.empty
                else []
            )
        start = (page - 1) * page_size
        window_ids = supplier_ids[start : start + page_size]
        performances = await run_in_threadpool(
            support.performances_for_suppliers,
            context.frames,
            window_ids,
            context.scope.supplier_names,
            context.analysis_date,
        )
    date_text = context.analysis_date.isoformat()
    total = len(supplier_ids)
    return success_envelope(
        {
            "items": performances,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": start + page_size < total,
            "analysis_date": date_text,
        },
        {
            "data_source_label": "synthetic",
            "source": "phase6_supplier_performance",
            "analysis_date": date_text,
            "limitations": [
                "Performance rows are descriptive metrics in supplier-id "
                "order — never a ranking, score, or preferred-supplier "
                "recommendation.",
                "Received quantities are inferred from delivered shipments "
                "linked to purchase orders.",
            ],
        },
    )


__all__ = ["router"]
