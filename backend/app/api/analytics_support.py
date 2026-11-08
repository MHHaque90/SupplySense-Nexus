"""Shared adapter glue for the Phase 12A dashboard API layer.

Layering fixed by the Phase 12A brief:

    HTTP request → router → Pydantic validation → authentication and
    authorization → this module (org-scoped loading + composition) →
    existing analytics engines (Phases 3–10) → response envelope with
    provenance.

This module only orchestrates existing public analytics functions and
the tested Phase 11 ``ai.tools._context`` loading layer. It introduces
no new calculations, no rankings, and no recommendations (Phase 11
locked decision C2 remains in force: "OPTIMAL" is a solver status and
is never translated into advice).

Organization isolation (same defense-in-depth rules as the Phase 11
tool layer):

1. Requested entity ids are validated against the caller's org scope
   (:func:`backend.app.ai.tools._context.require_scope`, fail closed).
2. Loaders receive ``organization_id`` or explicit id filters; an empty
   scope short-circuits to empty frames (an empty filter list never
   means "no filter").
3. Every frame is post-filtered by ``organization_id`` again.

CPU-bound composition (intelligence loops, forecast generation) is
executed by the routers through ``starlette.concurrency.run_in_threadpool``
so the FastAPI event loop is never blocked.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date

from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.ai import audit as audit_log
from backend.app.ai.tools import _context as ctx
from backend.app.ai.tools import _scenario as scenario_mod
from backend.app.analytics.inventory import health as inventory_health
from backend.app.analytics.inventory import position as inventory_position
from backend.app.analytics.inventory import reports as intel_reports
from backend.app.analytics.inventory.types import DEFAULT_INVENTORY_CONFIG
from backend.app.analytics.kpis import demand_kpis, inventory_kpis, procurement_kpis, service_kpis
from backend.app.analytics.procurement import concentration as concentration_mod
from backend.app.analytics.procurement import inbound as inbound_mod
from backend.app.analytics.procurement import open_orders as open_orders_mod
from backend.app.analytics.procurement import reports as procurement_reports
from backend.app.analytics.procurement import supplier_performance
from backend.app.analytics.procurement.types import DEFAULT_PROCUREMENT_CONFIG
from backend.app.analytics.replay import replay as replay_mod
from backend.app.analytics.risk import register as risk_register
from backend.app.analytics.risk import reports as risk_reports
from backend.app.analytics.risk.types import DEFAULT_RISK_CONFIG
from backend.app.analytics.simulation import events as events_mod
from backend.app.analytics.simulation import scenarios as scenarios_mod
from backend.app.analytics.simulation.types import DisruptionEvent
from backend.app.core.errors import APIError, ErrorCode
from backend.app.core.security import AuthContext
from backend.app.schemas.analytics import ScenarioRequest

ANALYST = "analyst"
PLANNER = "planner"
MANAGER = "manager"
EXECUTIVE = "executive"

#: Read access: dashboard and analytics are available to every analyst
#: level and above (administrators pass through ``require_roles``).
ANALYST_PLUS = (ANALYST, PLANNER, MANAGER, EXECUTIVE)

#: Compute access: simulation, replay, and optimization mirror the
#: existing Phase 11 tool role gates (planner, manager, executive).
PLANNER_PLUS = (PLANNER, MANAGER, EXECUTIVE)

#: Safety bound for KPI families returned by overview/dashboard reads.
KPI_FAMILY_CAP = 100

#: Safety bound for paginated series scans (positions/health/inbound).
MAX_API_SERIES = 500

DEFAULT_PAGE_SIZE = 50


@dataclass(frozen=True)
class RequestContext:
    """Org scope, org-scoped frames, and resolved analysis date."""

    scope: ctx.OrgScope
    frames: ctx.Frames
    analysis_date: date


async def load_request_context(
    session: AsyncSession,
    auth: AuthContext,
    *,
    product_id: str | None = None,
    warehouse_id: str | None = None,
    supplier_id: str | None = None,
    analysis_date: str | None = None,
) -> RequestContext:
    """Resolve scope → validation → frames → analysis date (fail closed).

    Raises ``ValueError`` for ids outside the caller's organization or a
    malformed ``analysis_date``; routers map those to 422 via
    :func:`map_value_errors`.
    """
    scope = await ctx.load_org_scope(session, auth.organization_id)
    ctx.require_scope(
        scope,
        product_id=product_id,
        warehouse_id=warehouse_id,
        supplier_id=supplier_id,
    )
    frames = await ctx.load_frames(session, scope)
    resolved = ctx.resolve_analysis_date(frames, analysis_date)
    return RequestContext(scope=scope, frames=frames, analysis_date=resolved)


@asynccontextmanager
async def map_value_errors() -> AsyncIterator[None]:
    """Map analytics ``ValueError``s onto the VALIDATION_ERROR envelope.

    Existing engines signal contract violations (unknown template, bad
    probability, out-of-scope target, no resolvable entities) with
    ``ValueError``; the API surface must never leak them as 500s.
    """
    try:
        yield
    except ValueError as exc:
        raise APIError(
            ErrorCode.VALIDATION_ERROR,
            details={"reason": str(exc)},
        ) from exc


def pagination_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=100),
) -> tuple[int, int]:
    """Shared ``page``/``page_size`` query parameters (1..n / 1..100)."""
    return page, page_size


def paginate(items: list, page: int, page_size: int) -> dict:
    """Apply the fixed list envelope: items/total/page/page_size/has_next."""
    total = len(items)
    start = (page - 1) * page_size
    window = items[start : start + page_size]
    return {
        "items": window,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": start + page_size < total,
    }


async def audit_run(
    session: AsyncSession,
    auth: AuthContext,
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    parameters: dict | None = None,
) -> None:
    """Append one audit event for a compute execution and commit it.

    Mirrors the Phase 11 pattern: ``audit.record`` joins the caller's
    transaction, so an explicit commit follows the write.
    """
    await audit_log.record(
        session,
        action=action,
        user_id=auth.user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        parameters=parameters,
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Inventory adapter helpers (Phase 5 engines, org-scoped frames)
# ---------------------------------------------------------------------------


def positions_for_keys(
    frames: ctx.Frames, keys: list[tuple[str, str]], analysis_date: date
) -> list[dict]:
    """Describe the latest inventory position per series key."""
    out: list[dict] = []
    for product_id, warehouse_id in keys:
        position = inventory_position.describe_position(
            product_id,
            warehouse_id,
            frames.snapshots,
            frames.transactions,
            analysis_date,
            DEFAULT_INVENTORY_CONFIG,
        )
        out.append(position.to_dict())
    return out


def health_for_keys(
    frames: ctx.Frames,
    keys: list[tuple[str, str]],
    forecasts: dict,
    analysis_date: date,
) -> list[dict]:
    """Classify inventory health per series key (Phase 5 rules)."""
    out: list[dict] = []
    for product_id, warehouse_id in keys:
        position = inventory_position.describe_position(
            product_id,
            warehouse_id,
            frames.snapshots,
            frames.transactions,
            analysis_date,
            DEFAULT_INVENTORY_CONFIG,
        )
        forecast = forecasts.get(f"{product_id}|{warehouse_id}")
        health = inventory_health.classify_health(
            position,
            forecast,
            None,
            None,
            DEFAULT_INVENTORY_CONFIG,
        )
        out.append(health.to_dict())
    return out


def performances_for_suppliers(
    frames: ctx.Frames,
    supplier_ids: list[str],
    supplier_names: dict[str, str],
    analysis_date: date,
) -> list[dict]:
    """Descriptive supplier performance facts (never ordered or scored)."""
    out: list[dict] = []
    for supplier_id in supplier_ids:
        performance = supplier_performance.describe_supplier(
            supplier_id,
            supplier_names.get(supplier_id, supplier_id),
            frames.po_lines,
            frames.shipments,
            analysis_date,
            DEFAULT_PROCUREMENT_CONFIG,
        )
        out.append(performance.to_dict())
    return out


def unique_suppliers(frame) -> list[dict]:
    """Deduplicate the supplier×product link frame into supplier rows."""
    if frame.empty:
        return []
    deduped = frame.drop_duplicates(subset=["supplier_id"])
    rows: list[dict] = []
    for _, row in deduped.sort_values("supplier_id").iterrows():
        rows.append(
            {
                "supplier_id": str(row["supplier_id"]),
                "supplier_name": str(row["supplier_name"]),
                "country": str(row.get("country", "")),
                "rating": row.get("rating"),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# KPI family composition (Phase 3 engines)
# ---------------------------------------------------------------------------


def _average_daily_demand(demand) -> float | None:
    """Extract the dataset-level average daily demand KPI value."""
    for item in demand_kpis.demand_summary(demand):
        if item.metric_name == "average_daily_demand" and item.value is not None:
            return float(item.value)
    return None


def build_inventory_kpis(frames: ctx.Frames) -> dict[str, list[dict]]:
    """Standard inventory KPI families with full KPI provenance rows."""
    snapshots = frames.snapshots
    transactions = frames.transactions
    average_daily = _average_daily_demand(frames.demand)
    families: dict[str, list[dict]] = {
        "current_on_hand": [
            item.to_dict() for item in inventory_kpis.current_on_hand(snapshots)[:KPI_FAMILY_CAP]
        ],
        "inventory_levels": [
            item.to_dict() for item in inventory_kpis.inventory_levels(snapshots)[:KPI_FAMILY_CAP]
        ],
        "stockout_stats": [
            item.to_dict() for item in inventory_kpis.stockout_stats(snapshots)[:KPI_FAMILY_CAP]
        ],
        "movement_summary": [
            item.to_dict()
            for item in inventory_kpis.movement_summary(transactions)[:KPI_FAMILY_CAP]
        ],
        "turnover_proxy": [
            item.to_dict()
            for item in inventory_kpis.turnover_proxy(transactions, snapshots)[:KPI_FAMILY_CAP]
        ],
        "days_of_supply": (
            [item.to_dict() for item in inventory_kpis.days_of_supply(snapshots, average_daily)]
            if average_daily is not None and average_daily > 0
            else []
        ),
    }
    return families


def build_procurement_kpis(frames: ctx.Frames) -> dict[str, list[dict]]:
    """Standard procurement KPI families (Phase 3 engines)."""
    orders = frames.po_lines
    shipments = frames.shipments
    return {
        "procurement_summary": [
            item.to_dict() for item in procurement_kpis.procurement_summary(orders)[:KPI_FAMILY_CAP]
        ],
        "lead_time_stats": [
            item.to_dict() for item in procurement_kpis.lead_time_stats(orders)[:KPI_FAMILY_CAP]
        ],
        "shipment_performance": [
            item.to_dict()
            for item in procurement_kpis.shipment_performance(shipments)[:KPI_FAMILY_CAP]
        ],
        "moq_compliance": [
            item.to_dict() for item in procurement_kpis.moq_compliance(orders)[:KPI_FAMILY_CAP]
        ],
        "concentration": [
            item.to_dict() for item in procurement_kpis.concentration(orders)[:KPI_FAMILY_CAP]
        ],
    }


def build_demand_kpis(frames: ctx.Frames) -> list[dict]:
    """Dataset-level demand KPI rows (Phase 3 engines)."""
    return [item.to_dict() for item in demand_kpis.demand_summary(frames.demand)[:KPI_FAMILY_CAP]]


# ---------------------------------------------------------------------------
# Cross-domain pipelines (Phase 5 + 6 + 7 compositions over public engines)
# ---------------------------------------------------------------------------


def build_intelligence(frames: ctx.Frames, forecasts: dict, analysis_date: date) -> list:
    """Build one Phase 5 inventory intelligence result per forecast series."""
    intelligence = []
    for key in sorted(forecasts):
        product_id, warehouse_id = key.split("|", 1)
        intelligence.append(
            intel_reports.build_intelligence(
                product_id,
                warehouse_id,
                frames.snapshots,
                frames.transactions,
                frames.demand,
                forecasts[key],
                frames.shipments,
                frames.po_lines,
                analysis_date,
                DEFAULT_INVENTORY_CONFIG,
            )
        )
    return intelligence


def build_supplier_results(frames: ctx.Frames, intelligence: list, analysis_date: date) -> list:
    """Build one Phase 6 procurement intelligence result per supplier."""
    if frames.supplier_links.empty:
        return []
    supplier_ids = sorted(frames.supplier_links["supplier_id"].astype(str).unique().tolist())
    names = dict(
        zip(
            frames.supplier_links["supplier_id"].astype(str),
            frames.supplier_links["supplier_name"].astype(str),
        )
    )
    return [
        procurement_reports.build_supplier_result(
            supplier_id,
            names.get(supplier_id, supplier_id),
            frames.po_lines,
            frames.shipments,
            frames.supplier_links,
            intelligence,
            analysis_date,
            DEFAULT_PROCUREMENT_CONFIG,
        )
        for supplier_id in supplier_ids
    ]


def build_risk_records(
    frames: ctx.Frames,
    intelligence: list,
    supplier_results: list,
    analysis_date: date,
    horizon: int,
) -> list:
    """Assemble the Phase 7 risk register records (no recalculation)."""
    open_orders = [order for result in supplier_results for order in result.open_orders]
    cooccurrences = [impact for result in supplier_results for impact in result.service_impacts]
    horizon_end = analysis_date.fromordinal(analysis_date.toordinal() + horizon).isoformat()
    records: list = []
    for item in intelligence:
        coverage = inbound_mod.describe_inbound_coverage(
            item.product_id,
            item.warehouse_id,
            item.forecast,
            item.position.current_on_hand if item.position else None,
            open_orders,
            horizon_end,
        )
        own_impacts = [
            impact
            for impact in cooccurrences
            if impact.product_id == item.product_id and impact.warehouse_id == item.warehouse_id
        ]
        records.extend(
            risk_reports.build_series_records(item, coverage, DEFAULT_RISK_CONFIG, own_impacts)
        )
    for result in supplier_results:
        records.extend(
            risk_reports.build_supplier_records(
                result,
                frames.supplier_links,
                frames.po_lines,
                frames.shipments,
                analysis_date,
                DEFAULT_RISK_CONFIG,
            )
        )
    concentration_rows = list(concentration_mod.volume_shares(frames.po_lines, "spend"))
    concentration_rows.extend(concentration_mod.po_count_shares(frames.po_lines))
    records.extend(
        risk_reports.build_structural_records(
            frames.supplier_links,
            frames.snapshots,
            intelligence,
            concentration_rows,
            analysis_date,
            DEFAULT_RISK_CONFIG,
        )
    )
    return records


def build_risk_report(records: list, analysis_date: date, horizon: int) -> dict:
    """Build the Phase 7 dataset-level risk report (fixed empty period)."""
    return risk_reports.build_report(
        records,
        analysis_date,
        horizon,
        {"start": None, "end": None},
        DEFAULT_RISK_CONFIG,
    )


def filter_risk_records(records: list, **filters) -> list:
    """Apply the existing Phase 7 register filters (supported keys only)."""
    return risk_register.filter_records(records, **filters)


def build_service_kpis(frames: ctx.Frames) -> list[dict]:
    """Service KPI rows derived from inventory snapshots (Phase 3)."""
    return [
        item.to_dict()
        for item in service_kpis.stockout_rate_from_snapshots(frames.snapshots)[:KPI_FAMILY_CAP]
    ]


# ---------------------------------------------------------------------------
# Procurement adapter helpers (Phase 6 engines, org-scoped frames)
# ---------------------------------------------------------------------------


def open_order_rows(
    frames: ctx.Frames, analysis_date: date, supplier_ids: list[str] | None
) -> list[dict]:
    """Descriptive open purchase-order rows (never a work queue)."""
    rows = open_orders_mod.describe_open_orders(
        frames.po_lines, frames.shipments, analysis_date, supplier_ids
    )
    return [row.to_dict() for row in rows]


def inbound_coverage_rows(
    frames: ctx.Frames,
    keys: list[tuple[str, str]],
    forecasts: dict,
    analysis_date: date,
    horizon: int,
) -> list[dict]:
    """Inbound coverage state per series (unknowns stay explicit)."""
    open_orders = open_orders_mod.describe_open_orders(
        frames.po_lines, frames.shipments, analysis_date, None
    )
    horizon_end = analysis_date.fromordinal(analysis_date.toordinal() + horizon).isoformat()
    rows: list[dict] = []
    for product_id, warehouse_id in keys:
        position = inventory_position.describe_position(
            product_id,
            warehouse_id,
            frames.snapshots,
            frames.transactions,
            analysis_date,
            DEFAULT_INVENTORY_CONFIG,
        )
        coverage = inbound_mod.describe_inbound_coverage(
            product_id,
            warehouse_id,
            forecasts.get(f"{product_id}|{warehouse_id}"),
            position.current_on_hand,
            open_orders,
            horizon_end,
        )
        rows.append(coverage.to_dict())
    return rows


def procurement_risk_signals(
    frames: ctx.Frames,
    intelligence: list,
    analysis_date: date,
    supplier_id: str | None = None,
) -> list[dict]:
    """Phase 6 risk-signal rows per supplier (descriptive, unranked)."""
    results = build_supplier_results(frames, intelligence, analysis_date)
    if supplier_id:
        results = [result for result in results if result.supplier_id == supplier_id]
    return [result.risk_signal.to_dict() for result in results]


# ---------------------------------------------------------------------------
# Forecast row slicing (Phase 4 inputs, windowed for the API)
# ---------------------------------------------------------------------------


def forecast_rows(
    forecasts: dict,
    *,
    horizon: int | None,
    profile: str | None,
    start_date: str | None,
    end_date: str | None,
) -> list[dict]:
    """Slice persisted/generated forecast inputs into API rows."""
    rows: list[dict] = []
    for key in sorted(forecasts):
        payload = forecasts[key].to_dict()
        if profile is not None and payload.get("demand_profile") != profile:
            continue
        dates = [str(value) for value in payload.get("forecast_dates") or []]
        indices = list(range(len(dates)))
        if start_date:
            indices = [index for index in indices if dates[index] >= start_date]
        if end_date:
            indices = [index for index in indices if dates[index] <= end_date]
        if horizon is not None:
            indices = indices[:horizon]

        def pick(name: str) -> list:
            values = payload.get(name) or []
            return [values[index] for index in indices]

        rows.append(
            {
                "series_id": key,
                "product_id": payload.get("product_id"),
                "warehouse_id": payload.get("warehouse_id"),
                "origin": payload.get("origin"),
                "forecast_dates": [dates[index] for index in indices],
                "horizon": len(indices),
                "point": pick("point"),
                "lower": pick("lower"),
                "upper": pick("upper"),
                "confidence_level": payload.get("confidence_level"),
                "interval_method": payload.get("interval_method"),
                "model_name": payload.get("model_name"),
                "model_version": payload.get("model_version"),
                "demand_profile": payload.get("demand_profile"),
                "validation_metric": payload.get("validation_metric"),
                "validation_score": payload.get("validation_score"),
                "validation_folds": payload.get("validation_folds"),
                "confidence": payload.get("confidence"),
                "explanation": payload.get("explanation"),
                "warnings": payload.get("warnings"),
                "source": payload.get("source"),
                "missing": payload.get("missing"),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Scenario composition for compute endpoints (Phase 8 contracts)
# ---------------------------------------------------------------------------


def _build_direct_event(body: ScenarioRequest) -> DisruptionEvent:
    """Mirror the CLI direct-event path (scripts/analyze_supply_chain.py)."""
    event_type = str(body.event_type)
    event = DisruptionEvent(
        event_id=f"{event_type.lower()}-api-{uuid.uuid4().hex[:8]}",
        event_type=event_type,
        name=event_type,
        start_date="",
        duration_days=(body.duration_days if body.duration_days is not None else 14),
        affected_suppliers=[body.supplier_id] if body.supplier_id else [],
        affected_products=[body.product_id] if body.product_id else [],
        affected_warehouses=[body.warehouse_id] if body.warehouse_id else [],
        supply_reduction=(body.supply_reduction if body.supply_reduction is not None else 0.0),
        lead_time_delay_days=(
            body.lead_time_delay_days if body.lead_time_delay_days is not None else 0
        ),
        demand_multiplier=(body.demand_multiplier if body.demand_multiplier is not None else 1.0),
        warehouse_available=body.event_type != "WAREHOUSE_DISRUPTION",
        assumptions=list(body.assumptions),
    )
    events_mod.validate_event(event, check_targets=False)
    return event


async def prepare_api_scenario(
    session: AsyncSession,
    auth: AuthContext,
    body: ScenarioRequest,
    run_label: str,
) -> scenario_mod.ScenarioBundle:
    """Compose one frozen Phase 8 scenario plus org-scoped forecasts.

    JSON-body mirror of
    :func:`backend.app.ai.tools._scenario.prepare_scenario`: exactly one of
    ``event_template`` (default ``SUPPLIER_OUTAGE``) or ``event_type``,
    declared overrides, org-defaulted targets, probability validation, and
    the persisted-first forecast inputs (empty forecasts fail closed).
    """
    params = body.model_dump()
    if body.event_template and body.event_type:
        raise ValueError("Provide at most one of event_template or event_type.")
    context = await load_request_context(
        session,
        auth,
        product_id=body.product_id,
        warehouse_id=body.warehouse_id,
        supplier_id=body.supplier_id,
        analysis_date=body.analysis_date,
    )
    notes: list[str] = []
    if body.event_type:
        event = _build_direct_event(body)
        notes.append(f"Direct event type {body.event_type} declared (no template).")
    else:
        event, notes = scenario_mod.build_event(params)
    if body.assumptions:
        event.assumptions = list(event.assumptions) + list(body.assumptions)
    horizon, count, seed = scenario_mod.validate_scenario_numbers(params)
    entities, entity_notes = scenario_mod.resolve_entities(context.scope, context.frames, params)
    notes.extend(entity_notes)
    scenario = scenarios_mod.build_scenario(
        scenario_id=f"{run_label}-{uuid.uuid4().hex[:10]}",
        event=event,
        analysis_date=context.analysis_date.isoformat(),
        horizon_days=horizon,
        affected_entities=entities,
        probability_mode=body.probability_mode,
        probability=body.probability,
        simulation_count=count,
        random_seed=seed,
        name=f"{run_label} scenario",
    )
    replay_id = replay_mod.resolve_replay_id(scenario)
    forecasts = await ctx.build_forecasts(
        session,
        context.frames,
        context.scope,
        context.analysis_date,
        body.product_id,
        body.warehouse_id,
    )
    if not forecasts:
        raise ValueError(
            "No forecast inputs could be built for this organization "
            "(missing demand history or forecast rows)."
        )
    return scenario_mod.ScenarioBundle(
        scope=context.scope,
        frames=context.frames,
        analysis_date=context.analysis_date,
        scenario=scenario,
        replay_id=replay_id,
        forecasts=forecasts,
        notes=notes,
    )


__all__ = [
    "ANALYST_PLUS",
    "DEFAULT_PAGE_SIZE",
    "KPI_FAMILY_CAP",
    "MAX_API_SERIES",
    "PLANNER_PLUS",
    "RequestContext",
    "audit_run",
    "build_demand_kpis",
    "build_intelligence",
    "build_inventory_kpis",
    "build_procurement_kpis",
    "build_risk_records",
    "build_risk_report",
    "build_service_kpis",
    "build_supplier_results",
    "filter_risk_records",
    "forecast_rows",
    "health_for_keys",
    "inbound_coverage_rows",
    "load_request_context",
    "map_value_errors",
    "open_order_rows",
    "paginate",
    "pagination_params",
    "performances_for_suppliers",
    "positions_for_keys",
    "prepare_api_scenario",
    "procurement_risk_signals",
    "unique_suppliers",
]
