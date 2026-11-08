"""Synthetic bill-of-materials generator with cycle validation.

Finished products only consume components that precede them in catalog
order, which makes cycles impossible by construction. A depth-first
graph validation still runs over every generated BOM.
"""

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig
from backend.app.data.generators.base import stream_rng


class BOMCycleError(ValueError):
    """Raised when a BOM graph contains a circular dependency."""


def validate_no_cycles(edges: dict[str, list[str]]) -> None:
    """Raise :class:`BOMCycleError` if the component graph has a cycle."""
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in visiting:
            cycle = " -> ".join([*path, node])
            raise BOMCycleError(f"Circular BOM dependency detected: {cycle}")
        if node in visited:
            return
        visiting.add(node)
        for child in edges.get(node, []):
            visit(child, [*path, node])
        visiting.discard(node)
        visited.add(node)

    for root in edges:
        visit(root, [])


def generate_bom(
    config: GenerationConfig,
    products: list[dict[str, str | None]],
) -> tuple[list[dict[str, str | None]], list[dict[str, str | int]]]:
    """Generate BOMs and components.

    The first products of each organization form a shared-component
    pool; later products become finished goods consuming 2-4 of those
    components. Returns ``(boms, components)``.
    """
    rng = stream_rng(config.seed, "bom")
    boms: list[dict[str, str | None]] = []
    components: list[dict[str, str | int]] = []
    edges: dict[str, list[str]] = {}
    start = config.start_date.isoformat()
    by_org: dict[str, list[dict[str, str | None]]] = {}
    for product in products:
        by_org.setdefault(str(product["organization_key"]), []).append(product)
    for org_products in by_org.values():
        if len(org_products) < 5:
            continue
        pool = org_products[: max(2, len(org_products) // 3)]
        finished = org_products[len(pool):]
        for item in finished:
            if rng.random() < 0.25:
                continue  # Some products are purchased, not manufactured.
            bom_key = f"BOM-{item['sku']}-v1"
            boms.append(
                {
                    "bom_key": bom_key,
                    "product_key": str(item["sku"]),
                    "version": "v1.0",
                    "effective_date": start,
                    "data_source_label": DataSourceLabel.SYNTHETIC.value,
                }
            )
            count = rng.randint(2, min(4, len(pool)))
            chosen = rng.sample(pool, count)
            edges.setdefault(str(item["sku"]), [])
            for component in chosen:
                edges[str(item["sku"])].append(str(component["sku"]))
                components.append(
                    {
                        "bom_key": bom_key,
                        "component_key": str(component["sku"]),
                        "quantity": str(rng.randint(1, 4)),
                        "unit_of_measure": rng.choice(["EA", "EA", "EA", "SET", "M"]),
                        "lead_time_days": rng.randint(3, 21),
                    }
                )
    validate_no_cycles(edges)
    return boms, components
