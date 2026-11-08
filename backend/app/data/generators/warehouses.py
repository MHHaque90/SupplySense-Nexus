"""Synthetic warehouse generator."""

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig

_WAREHOUSES: list[tuple[str, str]] = [
    ("WH-NORTH", "North Region"),
    ("WH-SOUTH", "South Region"),
    ("WH-EAST", "East Region"),
    ("WH-WEST", "West Region"),
    ("WH-CENTRAL", "Central Region"),
]


def generate_warehouses(
    config: GenerationConfig,
    organization_keys: list[str],
    per_org: int,
    expected_units_per_org: dict[str, int] | None = None,
) -> list[dict[str, str | int]]:
    """Generate synthetic warehouses with capacity above expected stock.

    Capacity is set to at least twice the expected on-hand units so
    generated inventory always fits the warehouse.
    """
    records: list[dict[str, str | int]] = []
    counter = 0
    for org_key in organization_keys:
        for index in range(per_org):
            code, location = _WAREHOUSES[counter % len(_WAREHOUSES)]
            expected = (expected_units_per_org or {}).get(org_key, 10000)
            records.append(
                {
                    "warehouse_code": code if len(organization_keys) == 1 else f"{code}-{counter + 1:02d}",
                    "name": code if len(organization_keys) == 1 else f"{code}-{counter + 1:02d}",
                    "location": location,
                    "capacity_units": max(5000, int(expected * 2)),
                    "current_utilization": "0.00",
                    "organization_key": org_key,
                    "data_source_label": DataSourceLabel.SYNTHETIC.value,
                }
            )
            counter += 1
    return records
