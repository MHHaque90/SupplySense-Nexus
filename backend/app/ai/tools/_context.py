"""Shared organization-scoped data loading for AI Decision Copilot tools.

Org isolation rules (defense in depth):

1. Entity ids requested by parameters must belong to the caller's
   organization (:func:`require_scope_*` raises otherwise).
2. Loaders are called with ``organization_id`` where supported; inventory
   loaders have no org parameter, so they receive explicit id filters built
   from the org scope (empty scope short-circuits to an empty frame — an
   empty filter list must never mean "no filter").
3. Every frame is post-filtered by ``organization_id`` (and shipments by
   org supplier ids) regardless of the filters above.

Compute-heavy steps (forecast generation, simulation, optimization) run
through :func:`run_in_threadpool` so the event loop stays responsive.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.analytics.config import AnalyticsConfig
from backend.app.analytics.datasets import demand as demand_loader
from backend.app.analytics.datasets import inventory as inventory_loader
from backend.app.analytics.datasets import procurement as procurement_loader
from backend.app.analytics.datasets import suppliers as suppliers_loader
from backend.app.analytics.inventory import forecast_inputs
from backend.app.models import Product, Supplier, Warehouse

MAX_SERIES = 25
DEFAULT_HORIZON_DAYS = 28
DEFAULT_SIMULATION_COUNT = 20
DEFAULT_SEASON = 7
DEFAULT_MIN_HISTORY = 60


@dataclass(frozen=True)
class OrgScope:
    """Id sets and names for one organization (the isolation boundary)."""

    organization_id: str
    product_ids: tuple[str, ...]
    warehouse_ids: tuple[str, ...]
    supplier_ids: tuple[str, ...]
    supplier_names: dict[str, str]


@dataclass
class Frames:
    """Canonical analytical frames scoped to one organization."""

    snapshots: pd.DataFrame
    transactions: pd.DataFrame
    po_lines: pd.DataFrame
    shipments: pd.DataFrame
    demand: pd.DataFrame
    supplier_links: pd.DataFrame


async def load_org_scope(session: AsyncSession, organization_id: str) -> OrgScope:
    """Resolve the caller's product/warehouse/supplier id sets."""
    product_ids = (
        await session.execute(
            select(Product.id).where(Product.organization_id == organization_id)
        )
    ).scalars().all()
    warehouse_ids = (
        await session.execute(
            select(Warehouse.id).where(Warehouse.organization_id == organization_id)
        )
    ).scalars().all()
    supplier_rows = (
        await session.execute(
            select(Supplier.id, Supplier.name).where(
                Supplier.organization_id == organization_id
            )
        )
    ).all()
    return OrgScope(
        organization_id=organization_id,
        product_ids=tuple(sorted(str(value) for value in product_ids)),
        warehouse_ids=tuple(sorted(str(value) for value in warehouse_ids)),
        supplier_ids=tuple(sorted(str(row[0]) for row in supplier_rows)),
        supplier_names={str(row[0]): str(row[1]) for row in supplier_rows},
    )


def require_scope(scope: OrgScope, **targets: str | None) -> None:
    """Validate requested entity ids against the org scope (fail closed)."""
    checks = (
        ("product_id", targets.get("product_id"), scope.product_ids),
        ("warehouse_id", targets.get("warehouse_id"), scope.warehouse_ids),
        ("supplier_id", targets.get("supplier_id"), scope.supplier_ids),
    )
    for name, value, allowed in checks:
        if value and value not in allowed:
            raise ValueError(
                f"{name} {value!r} is not available in your organization."
            )


def _filter_org(frame: pd.DataFrame, organization_id: str) -> pd.DataFrame:
    """Keep only rows of one organization when the column exists."""
    if frame.empty or "organization_id" not in frame.columns:
        return frame
    mask = frame["organization_id"].astype(str) == organization_id
    return frame[mask].reset_index(drop=True)


async def load_frames(session: AsyncSession, scope: OrgScope) -> Frames:
    """Load all canonical frames for one organization (org-scoped)."""
    supplier_links = await suppliers_loader.load_suppliers(
        session, organization_id=scope.organization_id
    )
    po_lines = await procurement_loader.load_purchase_orders(
        session, organization_id=scope.organization_id
    )
    if scope.supplier_ids:
        shipments = await procurement_loader.load_shipments(
            session, supplier_ids=list(scope.supplier_ids)
        )
        shipments = shipments[
            shipments["supplier_id"].astype(str).isin(scope.supplier_ids)
        ].reset_index(drop=True)
    else:
        shipments = pd.DataFrame(columns=procurement_loader.SHIPMENT_COLUMNS)
    if scope.product_ids and scope.warehouse_ids:
        snapshots = await inventory_loader.load_snapshots(
            session,
            product_ids=list(scope.product_ids),
            warehouse_ids=list(scope.warehouse_ids),
        )
        transactions = await inventory_loader.load_transactions(
            session,
            product_ids=list(scope.product_ids),
            warehouse_ids=list(scope.warehouse_ids),
        )
    else:
        snapshots = pd.DataFrame(columns=inventory_loader.SNAPSHOT_COLUMNS)
        transactions = pd.DataFrame(columns=inventory_loader.TRANSACTION_COLUMNS)
    demand = await demand_loader.load_demand(
        session, organization_id=scope.organization_id
    )
    return Frames(
        snapshots=_filter_org(snapshots, scope.organization_id),
        transactions=_filter_org(transactions, scope.organization_id),
        po_lines=_filter_org(po_lines, scope.organization_id),
        shipments=shipments,
        demand=_filter_org(demand, scope.organization_id),
        supplier_links=_filter_org(supplier_links, scope.organization_id),
    )


def resolve_analysis_date(
    frames: Frames, requested: str | None, today: date | None = None
) -> date:
    """Use the requested date or the latest date present in the data."""
    if requested:
        try:
            return date.fromisoformat(requested)
        except ValueError as exc:
            raise ValueError(
                f"analysis_date must be YYYY-MM-DD; got {requested!r}."
            ) from exc
    candidates: list[date] = []
    for frame, column in (
        (frames.snapshots, "snapshot_date"),
        (frames.po_lines, "order_date"),
        (frames.demand, "date"),
    ):
        if not frame.empty:
            values = pd.to_datetime(frame[column]).max()
            if pd.notna(values):
                candidates.append(values.date())
    if not candidates:
        return today or datetime.now(UTC).date()
    return max(candidates)


def series_keys(
    frames: Frames,
    analysis_date: date,
    product_id: str | None = None,
    warehouse_id: str | None = None,
    max_series: int = MAX_SERIES,
) -> list[tuple[str, str]]:
    """Return bounded, deterministic product/warehouse keys at a date."""
    if frames.snapshots.empty:
        return []
    mask = pd.to_datetime(frames.snapshots["snapshot_date"]).dt.date <= analysis_date
    subset = frames.snapshots[mask]
    keys = sorted(
        {
            (str(row["product_id"]), str(row["warehouse_id"]))
            for _, row in subset.iterrows()
        }
    )
    if product_id:
        keys = [key for key in keys if key[0] == product_id]
    if warehouse_id:
        keys = [key for key in keys if key[1] == warehouse_id]
    return keys[:max_series]


async def build_forecasts(
    session: AsyncSession,
    frames: Frames,
    scope: OrgScope,
    analysis_date: date,
    product_id: str | None = None,
    warehouse_id: str | None = None,
) -> dict:
    """Persisted-first forecast inputs per series (bounded, org-scoped).

    Missing series are generated deterministically in a worker thread from
    the org-scoped demand frame; generation never crosses the org boundary.
    """
    if not (scope.product_ids and scope.warehouse_ids):
        return {}
    persisted = await forecast_inputs.load_persisted_forecasts(
        session,
        product_ids=list(scope.product_ids),
        warehouse_ids=list(scope.warehouse_ids),
    )
    persisted = persisted[
        persisted["product_id"].astype(str).isin(scope.product_ids)
        & persisted["warehouse_id"].astype(str).isin(scope.warehouse_ids)
    ].reset_index(drop=True)
    inputs: dict = forecast_inputs.frame_to_inputs(persisted)
    keys = series_keys(frames, analysis_date, product_id, warehouse_id)
    missing = [key for key in keys if f"{key[0]}|{key[1]}" not in inputs]
    if missing and not frames.demand.empty:
        wanted = set(missing)
        missing_frame = frames.demand[
            frames.demand.apply(
                lambda row: (str(row["product_id"]), str(row["warehouse_id"]))
                in wanted,
                axis=1,
            )
        ]
        if not missing_frame.empty:
            generated = await run_in_threadpool(
                forecast_inputs.generate_inputs,
                missing_frame,
                analysis_date,
                AnalyticsConfig(
                    forecast_horizon=DEFAULT_HORIZON_DAYS,
                    min_history=DEFAULT_MIN_HISTORY,
                ),
                season=DEFAULT_SEASON,
                max_series=MAX_SERIES,
            )
            inputs.update(generated)
    if product_id or warehouse_id:
        wanted_keys = set(keys)
        inputs = {
            key: value
            for key, value in inputs.items()
            if tuple(key.split("|", 1)) in wanted_keys
        }
    return inputs


__all__ = [
    "DEFAULT_HORIZON_DAYS",
    "DEFAULT_MIN_HISTORY",
    "DEFAULT_SEASON",
    "DEFAULT_SIMULATION_COUNT",
    "MAX_SERIES",
    "Frames",
    "OrgScope",
    "build_forecasts",
    "load_frames",
    "load_org_scope",
    "require_scope",
    "resolve_analysis_date",
    "series_keys",
]
