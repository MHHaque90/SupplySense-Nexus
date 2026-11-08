"""Synthetic historical disruption events (NOT the simulation engine).

A small fixed set of past disruption events for testing analytics.
Each disruption carries ``data_source_label = "simulated"``. Impacts
reference affected product-warehouse combinations.
"""

from datetime import timedelta

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig
from backend.app.data.generators.base import format_probability, stream_rng

DISRUPTION_TYPES: list[str] = [
    "SUPPLIER_DELAY",
    "TRANSPORT_DELAY",
    "DEMAND_SPIKE",
    "COMPONENT_SHORTAGE",
    "WAREHOUSE_CAPACITY_REDUCTION",
]


def generate_disruptions(
    config: GenerationConfig,
    suppliers: list[dict[str, str | None]],
    products: list[dict[str, str | None]],
    warehouses: list[dict[str, str | int]],
) -> tuple[list[dict[str, str | None]], list[dict[str, str]]]:
    """Generate synthetic disruptions and their impacts."""
    rng = stream_rng(config.seed, "disruptions")
    label = DataSourceLabel.SIMULATED.value
    start = config.start_date
    span = max(30, config.history_days)
    events: list[dict[str, str | None]] = []
    impacts: list[dict[str, str]] = []
    for index, disruption_type in enumerate(DISRUPTION_TYPES):
        window = max(1, span - 30)
        offset = (60 * (index + 1) + rng.randint(0, 20)) % window
        begins = start + timedelta(days=offset)
        ends = begins + timedelta(days=rng.randint(5, 21))
        if ends > config.end_date:
            ends = config.end_date
        supplier_key = None
        if suppliers and disruption_type in ("SUPPLIER_DELAY", "COMPONENT_SHORTAGE"):
            supplier_key = str(rng.choice(suppliers)["supplier_code"])
        name = f"Synthetic {disruption_type.replace('_', ' ').title()} {index + 1:02d}"
        key = f"DIS-{index + 1:03d}"
        events.append(
            {
                "disruption_key": key,
                "name": name,
                "disruption_type": disruption_type,
                "severity": rng.choice(["low", "medium", "medium", "high", "critical"]),
                "start_date": begins.isoformat(),
                "end_date": ends.isoformat(),
                "supplier_key": supplier_key,
                "description": (
                    f"Synthetic {disruption_type} event generated for "
                    "demonstration and testing. Not a real event."
                ),
                "data_source_label": label,
            }
        )
        targets = rng.sample(products, min(4, len(products))) if products else []
        for product in targets:
            candidates = [
                w
                for w in warehouses
                if str(w["organization_key"]) == str(product["organization_key"])
            ]
            if not candidates:
                continue
            warehouse = rng.choice(candidates)
            baseline = float(str(product.get("baseline_demand", "20.0")))
            impacts.append(
                {
                    "disruption_key": key,
                    "product_key": str(product["sku"]),
                    "warehouse_key": str(warehouse["warehouse_code"]),
                    "estimated_demand_shortfall": str(int(baseline * rng.uniform(1.0, 5.0))),
                    "estimated_cost_impact": f"{baseline * rng.uniform(5.0, 40.0):.2f}",
                    "stockout_probability": format_probability(rng.uniform(0.1, 0.8)),
                }
            )
    return events, impacts
