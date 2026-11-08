"""Shared synthetic inputs for Phase 9 Decision Replay tests.

Everything here is SYNTHETIC and constructed in memory: no database
session, no real company data, no network access. Tests import these
builders so each replay test file stays small and readable.
"""

from datetime import date

import pandas as pd

from backend.app.analytics.inventory.types import ForecastInput
from backend.app.analytics.simulation import events as events_mod
from backend.app.analytics.simulation import scenarios as scenarios_mod
from backend.app.analytics.simulation import targets as targets_mod
from backend.app.analytics.simulation.types import SimulationScenario

ANALYSIS_DATE = date(2026, 6, 30)
HORIZON_DAYS = 28
PRODUCTS = ("P1", "P2")
WAREHOUSES = ("W1", "W2")
SUPPLIERS = ("S1", "S2")


def make_snapshots(on_hand: float = 40.0) -> pd.DataFrame:
    """Synthetic inventory snapshots for two products across two warehouses."""
    rows = []
    for product in PRODUCTS:
        for warehouse in WAREHOUSES:
            for day in (date(2026, 6, 25), date(2026, 6, 30)):
                rows.append({
                    "snapshot_date": day,
                    "organization_id": "ORG1",
                    "product_id": product,
                    "warehouse_id": warehouse,
                    "on_hand": float(on_hand),
                    "reserved": 0.0,
                    "in_transit": 0.0,
                    "sku": f"SKU-{product}",
                    "unit_cost": 10.0,
                })
    return pd.DataFrame(rows)


def make_po_lines() -> pd.DataFrame:
    """Synthetic open purchase-order lines inside the horizon."""
    return pd.DataFrame([
        {"po_id": "PO1", "po_number": "PO-1", "organization_id": "ORG1",
         "supplier_id": "S1", "supplier_name": "Alpha", "product_id": "P1",
         "order_date": date(2026, 6, 20), "expected_delivery_date": date(2026, 7, 5),
         "quantity": 60.0, "unit_cost": 12.5, "line_total": 750.0, "moq": 10.0,
         "lead_time_days": 7, "status": "open"},
        {"po_id": "PO2", "po_number": "PO-2", "organization_id": "ORG1",
         "supplier_id": "S2", "supplier_name": "Beta", "product_id": "P2",
         "order_date": date(2026, 6, 21), "expected_delivery_date": date(2026, 7, 8),
         "quantity": 40.0, "unit_cost": 9.0, "line_total": 360.0, "moq": 5.0,
         "lead_time_days": 10, "status": "open"},
    ])


def make_shipments() -> pd.DataFrame:
    """Synthetic in-transit shipments with no actual arrival yet."""
    return pd.DataFrame([
        {"shipment_id": "SH1", "po_id": "PO1", "supplier_id": "S1",
         "supplier_name": "Alpha", "shipped_date": date(2026, 6, 28),
         "expected_arrival_date": date(2026, 7, 5), "actual_arrival_date": None,
         "status": "in_transit", "delay_days": None},
        {"shipment_id": "SH2", "po_id": "PO2", "supplier_id": "S2",
         "supplier_name": "Beta", "shipped_date": date(2026, 6, 29),
         "expected_arrival_date": date(2026, 7, 8), "actual_arrival_date": None,
         "status": "in_transit", "delay_days": None},
    ])


def make_supplier_links(with_nullable_capacity: bool = True) -> pd.DataFrame:
    """Synthetic supplier-product links with observed unit costs and terms."""
    return pd.DataFrame([
        {"supplier_id": "S1", "supplier_name": "Alpha", "country": "X",
         "rating": 4.0, "organization_id": "ORG1", "product_id": "P1",
         "sku": "SKU-P1", "unit_cost": 12.5, "lead_time_days": 7,
         "min_order_qty": 10.0,
         "capacity_units": None if with_nullable_capacity else 1000.0},
        {"supplier_id": "S2", "supplier_name": "Beta", "country": "Y",
         "rating": 3.5, "organization_id": "ORG1", "product_id": "P2",
         "sku": "SKU-P2", "unit_cost": 9.0, "lead_time_days": 10,
         "min_order_qty": 5.0, "capacity_units": 800.0},
    ])


def make_forecasts(horizon_days: int = HORIZON_DAYS, demand: float = 10.0):
    """Synthetic prebuilt Phase 4 forecast inputs (never retrained here)."""
    forecasts = {}
    for product in PRODUCTS:
        for warehouse in WAREHOUSES:
            forecasts[f"{product}|{warehouse}"] = ForecastInput(
                product_id=product,
                warehouse_id=warehouse,
                origin=ANALYSIS_DATE.isoformat(),
                horizon=horizon_days,
                point=[float(demand)] * horizon_days,
                lower=[float(demand) * 0.8] * horizon_days,
                upper=[float(demand) * 1.2] * horizon_days,
                model_name="synthetic-forecast",
            )
    return forecasts


def make_scenario(
    scenario_id: str = "S-REPLAY",
    simulation_count: int = 5,
    random_seed: int = 7,
    horizon_days: int = HORIZON_DAYS,
    affected_suppliers: tuple[str, ...] = ("S1",),
) -> SimulationScenario:
    """One frozen deterministic supplier-disruption scenario."""
    event = events_mod.apply_template("SUPPLIER_OUTAGE", "E1")
    event.affected_suppliers = list(affected_suppliers)
    events_mod.validate_event(event)
    return scenarios_mod.build_scenario(
        scenario_id=scenario_id,
        event=event,
        analysis_date=ANALYSIS_DATE.isoformat(),
        horizon_days=horizon_days,
        simulation_count=simulation_count,
        random_seed=random_seed,
        affected_entities=targets_mod.resolve_explicit(
            supplier_ids=list(affected_suppliers)
        ),
    )


def make_inputs(horizon_days: int = HORIZON_DAYS, demand: float = 10.0) -> dict:
    """One dictionary with every frame a replay call needs."""
    return {
        "snapshots": make_snapshots(),
        "po_lines": make_po_lines(),
        "shipments": make_shipments(),
        "supplier_links": make_supplier_links(),
        "forecasts": make_forecasts(horizon_days, demand),
    }


def run_replay_for(decisions_list, scenario=None, inputs=None, **kwargs):
    """Run a replay over the shared synthetic inputs."""
    from backend.app.analytics.replay import replay as replay_mod

    scenario = scenario or make_scenario()
    inputs = inputs or make_inputs(scenario.horizon_days)
    return replay_mod.run_replay(
        scenario,
        decisions_list,
        inputs["forecasts"],
        inputs["snapshots"],
        inputs["shipments"],
        inputs["po_lines"],
        inputs["supplier_links"],
        ANALYSIS_DATE,
        **kwargs,
    )
