"""Supply-chain risk intelligence for SupplySense Nexus (Phase 7).

Transparent risk identification, aggregation, explanation, and
traceability over Phase 5 inventory and Phase 6 procurement
intelligence. Descriptive only: no optimization, no disruption
simulation, no Decision Replay, no automated decisions, no AI Copilot.

This dataset is synthetic and is generated solely for demonstration,
testing, analytics development, and portfolio purposes. Nothing here
is evidence about real suppliers, real procurement performance, real
supply-chain risk, or real business operations.
"""

from backend.app.analytics.risk import (
    aggregation,
    concentration_risk,
    dependency,
    inbound_risk,
    inventory_risk,
    leadtime_risk,
    procurement_risk,
    register,
    reports,
    risk_explanations,
    service_risk,
    supplier_risk,
    types,
    uncertainty_risk,
)

__all__ = [
    "aggregation",
    "concentration_risk",
    "dependency",
    "inbound_risk",
    "inventory_risk",
    "leadtime_risk",
    "procurement_risk",
    "register",
    "reports",
    "risk_explanations",
    "service_risk",
    "supplier_risk",
    "types",
    "uncertainty_risk",
]
