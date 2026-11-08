"""Synthetic sales order generator.

Sales orders are derived from demand observations (never generated
independently): each warehouse-day with positive demand becomes one
sales order aggregating that day's requested lines. Fulfillment is
resolved later by the inventory simulation, which may mark orders
partially fulfilled when stock runs short.
"""

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig


def generate_sales(
    config: GenerationConfig,
    demand: list[dict[str, str]],
    products: list[dict[str, str | None]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Derive sales orders and lines from demand history.

    Returns ``(orders, lines)``. Line ``unit_price`` is a deterministic
    markup over the product unit cost.
    """
    unit_costs = {str(p["sku"]): float(str(p.get("unit_cost") or "10.0")) for p in products}
    org_of = {str(p["sku"]): str(p["organization_key"]) for p in products}
    by_day: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in demand:
        if int(row["quantity"]) <= 0:
            continue
        key = (row["warehouse_key"], row["date"], org_of[row["product_key"]])
        by_day.setdefault(key, []).append(row)
    orders: list[dict[str, str]] = []
    lines: list[dict[str, str]] = []
    counter = 0
    for (warehouse_key, day, org_key), rows in sorted(by_day.items()):
        counter += 1
        order_key = f"SO-{counter:06d}"
        total = 0.0
        for row in rows:
            price = round(unit_costs[row["product_key"]] * 1.35, 2)
            quantity = int(row["quantity"])
            total += price * quantity
            lines.append(
                {
                    "order_key": order_key,
                    "product_key": row["product_key"],
                    "quantity": str(quantity),
                    "unit_price": f"{price:.2f}",
                    "data_source_label": DataSourceLabel.SYNTHETIC.value,
                }
            )
        orders.append(
            {
                "order_key": order_key,
                "customer_key": f"CUST-{(counter % 12) + 1:03d}",
                "order_date": day,
                "warehouse_key": warehouse_key,
                "total_amount": f"{total:.2f}",
                "status": "fulfilled",
                "organization_key": org_key,
                "data_source_label": DataSourceLabel.SYNTHETIC.value,
            }
        )
    return orders, lines
