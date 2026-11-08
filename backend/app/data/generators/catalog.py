"""Synthetic product catalog generator.

Demand profiles (STABLE, TRENDING, SEASONAL, VOLATILE, INTERMITTENT) are
kept in generator metadata because the Phase 1 product schema has no
profile column. Volume tiers drive baseline demand downstream.
"""

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig
from backend.app.data.generators.base import format_cost, stream_rng

CATEGORIES: list[str] = [
    "Electronics",
    "Home Appliances",
    "Industrial Components",
    "Consumer Accessories",
    "Replacement Parts",
]

PROFILES: list[str] = ["STABLE", "TRENDING", "SEASONAL", "VOLATILE", "INTERMITTENT"]

# Volume tier -> (baseline demand range, unit cost range).
TIERS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "high": ((80.0, 150.0), (15.0, 60.0)),
    "medium": ((25.0, 60.0), (30.0, 120.0)),
    "low": ((5.0, 15.0), (60.0, 250.0)),
}

_PRODUCT_NAMES: dict[str, list[str]] = {
    "Electronics": ["Circuit Board", "Sensor Module", "Control Unit", "Display Panel", "Power Adapter"],
    "Home Appliances": ["Blender Motor", "Heater Element", "Fan Assembly", "Pump Unit", "Thermostat"],
    "Industrial Components": ["Steel Bracket", "Bearing Set", "Valve Body", "Gear Assembly", "Coupling"],
    "Consumer Accessories": ["Carrying Case", "Cable Kit", "Mounting Stand", "Filter Pack", "Battery Pack"],
    "Replacement Parts": ["Seal Kit", "Fastener Set", "Gasket Pack", "Belt Drive", "Fuse Pack"],
}


def generate_categories() -> list[dict[str, str | None]]:
    """Generate the fixed synthetic category list."""
    return [{"name": name, "parent_key": None} for name in CATEGORIES]


def generate_products(
    config: GenerationConfig,
    organization_keys: list[str],
    per_org: int,
) -> list[dict[str, str | None]]:
    """Generate the synthetic product catalog.

    Products cycle through categories, volume tiers, and demand
    profiles deterministically so every profile is represented.
    """
    rng = stream_rng(config.seed, "products")
    records: list[dict[str, str | None]] = []
    counter = 0
    for org_key in organization_keys:
        for index in range(per_org):
            category = CATEGORIES[(index + counter) % len(CATEGORIES)]
            tier = ["high", "medium", "medium", "low", "low"][index % 5]
            if index % 7 == 6:
                tier = "low"
                profile = "INTERMITTENT"
            else:
                profile = PROFILES[index % len(PROFILES)]
            demand_range, cost_range = TIERS[tier]
            baseline = rng.uniform(*demand_range) * config.scenario_scale
            unit_cost = rng.uniform(*cost_range)
            name_pool = _PRODUCT_NAMES[category]
            name = f"{name_pool[index % len(name_pool)]} NX-{counter + 1:03d}"
            records.append(
                {
                    "sku": f"NX-{counter + 1:05d}",
                    "name": name,
                    "category_key": category,
                    "unit_cost": format_cost(unit_cost),
                    "weight_kg": f"{rng.uniform(0.1, 25.0):.3f}",
                    "organization_key": org_key,
                    "data_source_label": DataSourceLabel.SYNTHETIC.value,
                    # Generator metadata (not a schema column).
                    "demand_profile": profile,
                    "volume_tier": tier,
                    "baseline_demand": f"{baseline:.2f}",
                }
            )
            counter += 1
    return records
