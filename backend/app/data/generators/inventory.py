"""Synthetic inventory simulation generator.

Replays each product-warehouse day in chronological order::

    available += receipts arrival
    fulfilled = min(requested sales, available)
    available -= fulfilled

Inventory can never go negative: unfulfilled demand is recorded as a
lost sale and the sales order is corrected to ``partially_fulfilled``.
The opening balance is booked as an ``OPENING_BALANCE`` transaction so
the ledger reconciles exactly::

    opening + receipts - sales + adjustments = closing snapshot
"""

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig
from backend.app.data.generators.base import daterange, opening_balance, stream_rng


def simulate_inventory(
    config: GenerationConfig,
    demand: list[dict[str, str]],
    receipts: dict[tuple[str, str, str], int],
    orders: list[dict[str, str]],
    lines: list[dict[str, str]],
    products: list[dict[str, str | None]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, int], dict[str, int]]:
    """Replay inventory and produce transactions plus snapshots.

    Returns ``(transactions, snapshots, openings, fulfilled_sales)``
    where ``fulfilled_sales`` maps ``(product, warehouse, date)`` to the
    fulfilled quantity and ``openings`` maps ``(product, warehouse)`` to
    the opening balance.
    """
    rng = stream_rng(config.seed, "inventory")
    averages: dict[tuple[str, str], float] = {}
    counts: dict[tuple[str, str], int] = {}
    for row in demand:
        key = (row["product_key"], row["warehouse_key"])
        averages[key] = averages.get(key, 0.0) + int(row["quantity"])
        counts[key] = counts.get(key, 0) + 1
    for key in averages:
        averages[key] /= max(1, counts[key])
    requested: dict[tuple[str, str, str], int] = {}
    for row in demand:
        key = (row["product_key"], row["warehouse_key"], row["date"])
        requested[key] = requested.get(key, 0) + int(row["quantity"])
    order_of_day: dict[tuple[str, str], str] = {}
    for order in orders:
        order_of_day[(order["warehouse_key"], order["order_date"])] = order["order_key"]
    transactions: list[dict[str, str]] = []
    snapshots: list[dict[str, str]] = []
    openings: dict[str, int] = {}
    fulfilled: dict[str, int] = {}
    balances: dict[tuple[str, str], int] = {}
    label = DataSourceLabel.SYNTHETIC.value
    for (sku, warehouse_key), average in sorted(averages.items()):
        opening = opening_balance(average, config.coverage_days)
        balances[(sku, warehouse_key)] = opening
        openings[f"{sku}|{warehouse_key}"] = opening
        transactions.append(
            {
                "warehouse_key": warehouse_key,
                "product_key": sku,
                "transaction_type": "OPENING_BALANCE",
                "quantity": str(opening),
                "reference_key": None,
                "timestamp": config.start_date.isoformat(),
                "data_source_label": label,
            }
        )
    for current in daterange(config.start_date, config.end_date):
        day = current.isoformat()
        for (sku, warehouse_key) in sorted(balances.keys()):
            arrival = receipts.get((sku, warehouse_key, day), 0)
            if arrival > 0:
                balances[(sku, warehouse_key)] += arrival
                transactions.append(
                    {
                        "warehouse_key": warehouse_key,
                        "product_key": sku,
                        "transaction_type": "RECEIPT",
                        "quantity": str(arrival),
                        "reference_key": None,
                        "timestamp": day,
                        "data_source_label": label,
                    }
                )
            want = requested.get((sku, warehouse_key, day), 0)
            got = min(want, balances[(sku, warehouse_key)])
            balances[(sku, warehouse_key)] -= got
            fulfilled[f"{sku}|{warehouse_key}|{day}"] = got
            if got > 0:
                transactions.append(
                    {
                        "warehouse_key": warehouse_key,
                        "product_key": sku,
                        "transaction_type": "SALE",
                        "quantity": str(got),
                        "reference_key": order_of_day.get((warehouse_key, day)),
                        "timestamp": day,
                        "data_source_label": label,
                    }
                )
            if want > got:
                key = order_of_day.get((warehouse_key, day))
                for order in orders:
                    if order["order_key"] == key:
                        order["status"] = "partially_fulfilled"
                        break
        # Sparse cycle-count adjustments, always non-negative outcome.
        if rng.random() < 0.02:
            sku, warehouse_key = rng.choice(sorted(balances.keys()))
            adjustment = rng.randint(1, 5)
            balances[(sku, warehouse_key)] += adjustment
            transactions.append(
                {
                    "warehouse_key": warehouse_key,
                    "product_key": sku,
                    "transaction_type": "ADJUSTMENT",
                    "quantity": str(adjustment),
                    "reference_key": None,
                    "timestamp": day,
                    "data_source_label": label,
                }
            )
        if current.weekday() == 6 or current == config.end_date:
            for (sku, warehouse_key), balance in sorted(balances.items()):
                snapshots.append(
                    {
                        "warehouse_key": warehouse_key,
                        "product_key": sku,
                        "available_qty": str(balance),
                        "reserved_qty": "0",
                        "in_transit_qty": "0",
                        "snapshot_date": day,
                        "data_source_label": label,
                    }
                )
    _ = lines
    _ = products
    return transactions, snapshots, openings, fulfilled
