"""Built-in tool registrations for the AI Decision Copilot (Phase 11).

Every shipped tool lives here. The registry enforces the hard boundaries:

- seven read-only analytical tools (org-scoped),
- three compute tools (simulation / replay / optimization),
- **zero executable mutation tools** (MUTATION stays empty by construction),
- three approval-required *declarations* with no handler and no execution
  path (referenced only by approval records).

Tool names never use recommendation or ranking vocabulary (decision C2).
"""

from backend.app.ai.registry import (
    APPROVAL_REQUIRED,
    DECISION_REPLAY,
    MUTATION,
    OPTIMIZATION,
    READ_ONLY_ANALYTICS,
    SIMULATION,
    ToolRegistry,
    ToolSpec,
)
from backend.app.ai.tools import (
    analytics_tools,
    optimization_tools,
    replay_tools,
    simulation_tools,
)
from backend.app.ai.tools._scenario import scenario_properties

_ANALYSTICS_ROLES: tuple[str, ...] = ()
_PLANNING_ROLES: tuple[str, ...] = ("planner", "manager", "executive")


def _object(properties: dict, required: list[str] | None = None) -> dict:
    """Build a JSON-schema object entry."""
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


_ID = {"type": "string", "maxLength": 36}
_DATE = {"type": "string", "maxLength": 10}


def build_default_registry() -> ToolRegistry:
    """Construct a fresh registry with all shipped tools and declarations."""
    registry = ToolRegistry()

    registry.register(
        ToolSpec(
            name="get_forecast",
            description=(
                "Retrieve persisted forecast rows (point/lower/upper bounds, "
                "confidence level) for products in your organization. "
                "Forecasts are estimates, not actuals."
            ),
            category=READ_ONLY_ANALYTICS,
            parameters=_object(
                {
                    "product_id": {**_ID, "description": "Product id filter."},
                    "warehouse_id": {**_ID, "description": "Warehouse id filter."},
                    "horizon": {
                        "type": "integer",
                        "description": "Max forecast days per series (1..365).",
                    },
                }
            ),
            handler=analytics_tools.get_forecast,
            required_roles=_ANALYSTICS_ROLES,
        )
    )
    registry.register(
        ToolSpec(
            name="get_inventory_position",
            description=(
                "Current inventory position per product/warehouse series at "
                "an analysis date (latest snapshot on or before the date)."
            ),
            category=READ_ONLY_ANALYTICS,
            parameters=_object(
                {
                    "product_id": {**_ID, "description": "Product id filter."},
                    "warehouse_id": {**_ID, "description": "Warehouse id filter."},
                    "analysis_date": {**_DATE, "description": "YYYY-MM-DD."},
                }
            ),
            handler=analytics_tools.get_inventory_position,
            required_roles=_ANALYSTICS_ROLES,
        )
    )
    registry.register(
        ToolSpec(
            name="get_inventory_health",
            description=(
                "Rule-based inventory health classification per series "
                "(STOCKOUT/CRITICAL/AT_RISK/HEALTHY/EXCESS/UNKNOWN) with "
                "explicit missing-evidence fields."
            ),
            category=READ_ONLY_ANALYTICS,
            parameters=_object(
                {
                    "product_id": {**_ID, "description": "Product id filter."},
                    "warehouse_id": {**_ID, "description": "Warehouse id filter."},
                    "analysis_date": {**_DATE, "description": "YYYY-MM-DD."},
                }
            ),
            handler=analytics_tools.get_inventory_health,
            required_roles=_ANALYSTICS_ROLES,
        )
    )
    registry.register(
        ToolSpec(
            name="get_supplier_scorecard",
            description=(
                "Descriptive supplier delivery performance (on-time counts, "
                "delay statistics, lead times, missing evidence). Produces "
                "no ordering or scoring of suppliers."
            ),
            category=READ_ONLY_ANALYTICS,
            parameters=_object(
                {
                    "supplier_id": {**_ID, "description": "Supplier id filter."},
                    "analysis_date": {**_DATE, "description": "YYYY-MM-DD."},
                }
            ),
            handler=analytics_tools.get_supplier_scorecard,
            required_roles=_ANALYSTICS_ROLES,
        )
    )
    registry.register(
        ToolSpec(
            name="get_inventory_kpis",
            description=(
                "Standard inventory KPIs with numerator, denominator, grain, "
                "dimensions, and source tables (current on-hand, stockout "
                "stats, movement summary)."
            ),
            category=READ_ONLY_ANALYTICS,
            parameters=_object({"analysis_date": {**_DATE, "description": "YYYY-MM-DD."}}),
            handler=analytics_tools.get_inventory_kpis,
            required_roles=_ANALYSTICS_ROLES,
        )
    )
    registry.register(
        ToolSpec(
            name="get_data_quality_report",
            description=(
                "Table row counts plus the persisted data-quality check "
                "results from the last generation run (read-only)."
            ),
            category=READ_ONLY_ANALYTICS,
            parameters=_object({}),
            handler=analytics_tools.get_data_quality_report,
            required_roles=_ANALYSTICS_ROLES,
        )
    )
    registry.register(
        ToolSpec(
            name="get_risk_report",
            description=(
                "Phase 7 risk register summary across inventory, inbound, "
                "service, supplier, and structural domains with per-record "
                "evidence (bounded output)."
            ),
            category=READ_ONLY_ANALYTICS,
            parameters=_object(
                {
                    "severity": {"type": "string", "maxLength": 20, "description": "Severity filter."},
                    "domain": {"type": "string", "maxLength": 30, "description": "Risk domain filter."},
                    "horizon_days": {"type": "integer", "description": "Forecast horizon 1..180 (default 28)."},
                    "product_id": {**_ID, "description": "Product id filter."},
                    "warehouse_id": {**_ID, "description": "Warehouse id filter."},
                    "supplier_id": {**_ID, "description": "Supplier id filter."},
                    "analysis_date": {**_DATE, "description": "YYYY-MM-DD."},
                }
            ),
            handler=analytics_tools.get_risk_report,
            required_roles=_ANALYSTICS_ROLES,
        )
    )

    registry.register(
        ToolSpec(
            name="run_disruption_simulation",
            description=(
                "Run the Monte Carlo disruption simulation for one frozen, "
                "declared scenario and return the full simulated report "
                "(labeled simulated)."
            ),
            category=SIMULATION,
            parameters=_object(scenario_properties()),
            handler=simulation_tools.run_disruption_simulation,
            required_roles=_PLANNING_ROLES,
        )
    )
    registry.register(
        ToolSpec(
            name="run_decision_comparison",
            description=(
                "Replay declared decision arms against the shared baseline "
                "under one frozen scenario and return factual simulated "
                "deltas (no ordering of options)."
            ),
            category=DECISION_REPLAY,
            parameters=_object(
                {**scenario_properties(), **replay_tools.decision_properties()}
            ),
            handler=replay_tools.run_decision_comparison,
            required_roles=_PLANNING_ROLES,
        )
    )
    registry.register(
        ToolSpec(
            name="run_optimization_analysis",
            description=(
                "Run the Phase 10 procurement MILP for one of four declared "
                "objectives over a frozen scenario and return the full "
                "solver report (solver status vocabulary, labeled simulated)."
            ),
            category=OPTIMIZATION,
            parameters=_object(
                {**scenario_properties(), **optimization_tools.optimization_properties()}
            ),
            handler=optimization_tools.run_optimization_analysis,
            required_roles=_PLANNING_ROLES,
        )
    )

    # --- Declarations only: no handler, no execution path, manager-decided.
    registry.register(
        ToolSpec(
            name="procurement_order_change",
            description=(
                "Declare a procurement order change (create, modify, or "
                "cancel purchase-order lines). Declaration only: recording "
                "a human decision via POST /ai/approval never executes it."
            ),
            category=APPROVAL_REQUIRED,
            parameters=_object(
                {
                    "supplier_id": {**_ID, "description": "Affected supplier."},
                    "order_reference": {"type": "string", "maxLength": 64},
                    "details": {"type": "string", "maxLength": 1000},
                }
            ),
            handler=None,
            required_roles=(),
            executable=False,
            requires_approval=True,
        )
    )
    registry.register(
        ToolSpec(
            name="inventory_adjustment",
            description=(
                "Declare an inventory adjustment (quantity correction or "
                "transfer). Declaration only: recording a human decision "
                "via POST /ai/approval never executes it."
            ),
            category=APPROVAL_REQUIRED,
            parameters=_object(
                {
                    "product_id": {**_ID, "description": "Affected product."},
                    "warehouse_id": {**_ID, "description": "Affected warehouse."},
                    "details": {"type": "string", "maxLength": 1000},
                }
            ),
            handler=None,
            required_roles=(),
            executable=False,
            requires_approval=True,
        )
    )
    registry.register(
        ToolSpec(
            name="scenario_deployment",
            description=(
                "Declare deployment of a simulated scenario into operational "
                "planning. Declaration only: recording a human decision via "
                "POST /ai/approval never executes it."
            ),
            category=APPROVAL_REQUIRED,
            parameters=_object(
                {
                    "scenario_reference": {"type": "string", "maxLength": 64},
                    "details": {"type": "string", "maxLength": 1000},
                }
            ),
            handler=None,
            required_roles=(),
            executable=False,
            requires_approval=True,
        )
    )

    assert registry.list(category=MUTATION) == []  # zero mutation tools
    return registry


__all__ = ["build_default_registry"]
