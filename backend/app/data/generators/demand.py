"""Synthetic demand history generator.

Daily demand per product and warehouse follows::

    baseline + trend + yearly seasonality + weekly pattern + noise + events

Values are non-negative integers. Every product-warehouse-day within the
history window receives exactly one row so date continuity holds.
Intermittent products legitimately contain zero-demand days.
"""

import math
from datetime import date

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig
from backend.app.data.generators.base import daterange, format_quantity, stream_rng


def _daily_demand(
    rng: object,
    profile: str,
    baseline: float,
    day_index: int,
    current: date,
) -> int:
    """Compute one deterministic daily demand quantity."""
    import random as _random

    assert isinstance(rng, _random.Random)
    value = baseline
    if profile == "TRENDING":
        value = baseline * (1.0 + 0.35 * day_index / 365.0)
    elif profile == "SEASONAL":
        value = baseline * (1.0 + 0.45 * math.sin(2.0 * math.pi * (day_index + 40) / 365.0))
    elif profile == "VOLATILE":
        value = baseline * (1.0 + 0.25 * math.sin(2.0 * math.pi * day_index / 30.0))
    elif profile == "INTERMITTENT":
        if rng.random() < 0.55:
            return 0
        return max(0, int(round(baseline * rng.uniform(1.0, 3.0))))
    # Weekly pattern: weekend dip for most profiles.
    if current.weekday() >= 5:
        value *= 0.65
    # Promotional spikes: three deterministic windows per year.
    if day_index % 120 in (10, 11, 12):
        value *= 1.8
    noise = rng.gauss(0.0, baseline * (0.25 if profile == "VOLATILE" else 0.12))
    return max(0, int(round(value + noise)))


def generate_demand(
    config: GenerationConfig,
    products: list[dict[str, str | None]],
    warehouses: list[dict[str, str | int]],
) -> list[dict[str, str]]:
    """Generate daily demand observations for every product/warehouse."""
    rng = stream_rng(config.seed, "demand")
    days = daterange(config.start_date, config.end_date)
    # Warehouse-level demand shares, fixed per warehouse code.
    shares: dict[str, float] = {}
    for warehouse in warehouses:
        code = str(warehouse["warehouse_code"])
        shares[code] = 0.7 + 0.6 * rng.random()
    total_share = sum(shares.values()) or 1.0
    records: list[dict[str, str]] = []
    for product in products:
        profile = str(product.get("demand_profile", "STABLE"))
        baseline = float(str(product.get("baseline_demand", "20.0")))
        for warehouse in warehouses:
            if str(warehouse["organization_key"]) != str(product["organization_key"]):
                continue
            share = shares[str(warehouse["warehouse_code"])] / total_share
            for day_index, current in enumerate(days):
                quantity = _daily_demand(rng, profile, baseline * share, day_index, current)
                records.append(
                    {
                        "product_key": str(product["sku"]),
                        "warehouse_key": str(warehouse["warehouse_code"]),
                        "date": current.isoformat(),
                        "quantity": format_quantity(float(quantity)),
                        "data_source_label": DataSourceLabel.SYNTHETIC.value,
                    }
                )
    return records
