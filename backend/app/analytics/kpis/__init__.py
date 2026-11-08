"""Supply-chain KPIs over analytical frames (Phase 3).

Every KPI carries numerator, denominator, grain, dimensions, source
tables, and the synthetic flag so results stay auditable.
"""

from backend.app.analytics.kpis import demand_kpis, inventory_kpis, procurement_kpis, service_kpis

__all__ = ["demand_kpis", "inventory_kpis", "procurement_kpis", "service_kpis"]
