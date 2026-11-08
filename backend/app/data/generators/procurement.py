"""Synthetic purchase order generator (baseline replenishment policy).

DATA GENERATION RULE ONLY — not an optimized procurement policy.

If projected inventory (on hand plus scheduled arrivals) falls below a
reorder threshold, one purchase order is created::

    reorder_point = average_daily * lead_time * service_factor
    order_quantity = max(MOQ, order_up_to_level - projected, capped by capacity)

The supplier is chosen deterministically among linked suppliers,
preferring lower unit cost with seeded jitter. Returns purchase orders,
lines, and the scheduled receipt map consumed by the inventory module.
"""

from datetime import timedelta

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig
from backend.app.data.generators.base import stream_rng


def generate_purchase_orders(
    config: GenerationConfig,
    demand: list[dict[str, str]],
    supplier_products: list[dict[str, str | None]],
) -> tuple[list[dict[str, str | None]], list[dict[str, str]], dict[tuple[str, str, str], int]]:
    """Generate purchase orders driven by demand and lead times."""
    rng = stream_rng(config.seed, "procurement")
    # Average daily demand per (product, warehouse).
    totals: dict[tuple[str, str], int] = {}
    for row in demand:
        key = (row["product_key"], row["warehouse_key"])
        totals[key] = totals.get(key, 0) + int(row["quantity"])
    averages = {key: total / config.history_days for key, total in totals.items()}
    # Supplier options per product SKU.
    options: dict[str, list[dict[str, str | None]]] = {}
    for link in supplier_products:
        options.setdefault(str(link["product_key"]), []).append(link)
    orders: list[dict[str, str | None]] = []
    lines: list[dict[str, str]] = []
    receipts: dict[tuple[str, str, str], int] = {}
    counter = 0
    for (sku, warehouse_key), average in sorted(averages.items()):
        choices = options.get(sku, [])
        if not choices or average <= 0:
            continue
        # Deterministic cheapest-with-jitter supplier choice.
        scored = sorted(
            choices,
            key=lambda link: float(str(link["unit_cost"])) * rng.uniform(0.9, 1.1),
        )
        link = scored[0]
        lead_time = int(link["lead_time_days"] or 14)
        moq = max(1, int(str(link["min_order_qty"])))
        capacity = max(moq * 4, int(str(link.get("capacity_units") or moq * 10)))
        reorder_point = average * lead_time * config.reorder_service_factor
        order_up_to = average * (lead_time + config.order_up_to_days)
        # Simulate coverage in lead-time buckets across history.
        day = config.start_date
        projected = average * config.coverage_days
        end = config.end_date
        while day <= end:
            projected -= average
            # Receipts are anticipated at order time (projected += quantity
            # below), so arrival days add nothing further here. The
            # receipts schedule itself is preserved for the inventory
            # simulation, which consumes it exactly once.
            if projected <= reorder_point:
                quantity = max(moq, int(round(order_up_to - projected)))
                quantity = min(quantity, capacity)
                if quantity <= 0:
                    day += timedelta(days=1)
                    continue
                counter += 1
                order_key = f"PO-{counter:06d}"
                arrival = day + timedelta(days=lead_time)
                receipts[(sku, warehouse_key, arrival.isoformat())] = (
                    receipts.get((sku, warehouse_key, arrival.isoformat()), 0) + quantity
                )
                expected = arrival.isoformat()
                status = "received" if arrival <= end else "ordered"
                unit_cost = str(link["unit_cost"])
                orders.append(
                    {
                        "order_key": order_key,
                        "supplier_key": str(link["supplier_key"]),
                        "order_date": day.isoformat(),
                        "expected_delivery_date": expected,
                        "total_cost": f"{float(unit_cost) * quantity:.2f}",
                        "status": status,
                        "product_key": sku,
                        "warehouse_key": warehouse_key,
                        "data_source_label": DataSourceLabel.SYNTHETIC.value,
                    }
                )
                lines.append(
                    {
                        "order_key": order_key,
                        "product_key": sku,
                        "quantity": str(quantity),
                        "unit_cost": unit_cost,
                        "line_total": f"{float(unit_cost) * quantity:.2f}",
                        "data_source_label": DataSourceLabel.SYNTHETIC.value,
                    }
                )
                projected += quantity
            day += timedelta(days=1)
    # Split oversized receipts are handled by shipments; mark partial POs.
    for order in orders:
        arrival = str(order["expected_delivery_date"])
        if arrival > end.isoformat():
            order["status"] = "ordered"
    return orders, lines, receipts
