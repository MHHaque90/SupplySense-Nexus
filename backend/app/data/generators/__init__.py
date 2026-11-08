"""Deterministic synthetic ERP record generators (Phase 2).

Each generator is a pure function of the configuration and seed: it
returns lists of plain dictionaries with deterministic business fields.
Database identity (UUIDs) and timestamps are assigned at ingestion time,
so reproducibility comparisons use business fields only.
"""

from backend.app.data.generators import (
    bom,
    catalog,
    demand,
    disruptions,
    inventory,
    organizations,
    procurement,
    sales,
    shipments,
    suppliers,
    users,
    warehouses,
)

__all__ = [
    "bom",
    "catalog",
    "demand",
    "disruptions",
    "inventory",
    "organizations",
    "procurement",
    "sales",
    "shipments",
    "suppliers",
    "users",
    "warehouses",
]
