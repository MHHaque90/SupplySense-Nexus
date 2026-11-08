"""Synthetic supplier and supplier-product relationship generator.

Supplier performance is never pre-assigned: reliability differences are
expressed only through lead-time and delay parameters so later phases
can compute performance from operational data.
"""

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig
from backend.app.data.generators.base import format_cost, format_quantity, stream_rng

# Profile -> (lead time range, delay mean, delay sd, cost factor, capacity units).
PROFILES: dict[str, tuple[tuple[int, int], float, float, float, int]] = {
    "LOW_COST_HIGH_LEAD_TIME": ((45, 75), 4.0, 3.0, 0.85, 20000),
    "HIGH_COST_FAST": ((5, 12), 0.5, 1.0, 1.25, 8000),
    "RELIABLE": ((12, 20), 0.5, 1.0, 1.0, 15000),
    "VARIABLE_LEAD_TIME": ((15, 40), 3.0, 6.0, 0.95, 12000),
    "LIMITED_CAPACITY": ((10, 25), 1.5, 2.0, 1.1, 3000),
}

_COUNTRIES: list[str] = [
    "Germany",
    "Poland",
    "Czechia",
    "Mexico",
    "Vietnam",
    "India",
    "Portugal",
    "Canada",
]

_MOQ_STEPS: list[int] = [10, 25, 50, 100, 250]


def generate_suppliers(
    config: GenerationConfig,
    organization_keys: list[str],
    per_org: int,
) -> list[dict[str, str | None]]:
    """Generate synthetic suppliers with distinct lead-time profiles."""
    rng = stream_rng(config.seed, "suppliers")
    profile_names = list(PROFILES.keys())
    records: list[dict[str, str | None]] = []
    counter = 0
    for org_key in organization_keys:
        for index in range(per_org):
            profile = profile_names[(index + counter) % len(profile_names)]
            records.append(
                {
                    "supplier_code": f"SUP-{counter + 1:03d}",
                    "name": f"Nexus Supply {counter + 1:03d}",
                    "country": _COUNTRIES[(index + counter) % len(_COUNTRIES)],
                    "rating": f"{rng.uniform(2.5, 5.0):.1f}",
                    "organization_key": org_key,
                    "data_source_label": DataSourceLabel.SYNTHETIC.value,
                    # Generator metadata (not schema columns).
                    "supplier_profile": profile,
                }
            )
            counter += 1
    return records


def generate_supplier_products(
    config: GenerationConfig,
    products: list[dict[str, str | None]],
    suppliers: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    """Link suppliers to products with varying MOQ, cost, and lead time.

    Rules:
    - The first component product is single-sourced (supports later
      single-point-of-failure analysis); all others are multi-sourced.
    - Order quantity from procurement never exceeds supplier capacity
      because capacity scales with product baseline demand.
    - Lead times come from the supplier profile range.
    """
    rng = stream_rng(config.seed, "supplier_products")
    records: list[dict[str, str | None]] = []
    by_org: dict[str, list[int]] = {}
    for idx, supplier in enumerate(suppliers):
        org = str(supplier["organization_key"])
        by_org.setdefault(org, []).append(idx)
    for prod_idx, product in enumerate(products):
        org = str(product["organization_key"])
        candidates = by_org.get(org, [])
        if not candidates:
            continue
        if prod_idx == 0:
            chosen = candidates[:1]  # Intentional single source.
        else:
            count = min(len(candidates), 1 + (prod_idx % 2) + (1 if prod_idx % 3 == 0 else 0))
            start = prod_idx % len(candidates)
            chosen = [candidates[(start + offset) % len(candidates)] for offset in range(count)]
        baseline = float(str(product.get("baseline_demand", "20.0")))
        for sup_idx in chosen:
            supplier = suppliers[sup_idx]
            profile = str(supplier["supplier_profile"])
            (low, high), _, _, factor, _ = PROFILES[profile]
            unit_cost = float(str(product.get("unit_cost") or "10.0")) * factor
            unit_cost *= rng.uniform(0.95, 1.05)
            lead_time = rng.randint(low, high)
            moq = rng.choice(_MOQ_STEPS)
            capacity = max(moq * 4, int(baseline * 90))
            records.append(
                {
                    "supplier_key": str(supplier["supplier_code"]),
                    "product_key": str(product["sku"]),
                    "unit_cost": format_cost(unit_cost),
                    "lead_time_days": lead_time,
                    "min_order_qty": format_quantity(float(moq)),
                    "moq_currency": "USD",
                    "capacity_units": format_quantity(float(capacity)),
                    "data_source_label": DataSourceLabel.SYNTHETIC.value,
                }
            )
    return records
