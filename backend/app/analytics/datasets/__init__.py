"""Analytical dataset loaders (Phase 3).

Loaders are the only analytics modules that touch the database. They
issue single column-only SELECTs (no N+1, no ORM object graphs) and
return canonical pandas frames with explicit dtypes.
"""

from backend.app.analytics.datasets import demand, inventory, procurement, sales, suppliers

__all__ = ["demand", "inventory", "procurement", "sales", "suppliers"]
