"""Synthetic shipment generator.

Most shipments arrive on time; some arrive early or late according to
the supplier profile delay parameters. Large purchase orders are
occasionally split into two partial shipments. Every shipment carries
a coherent event trail (SHIPPED, IN_TRANSIT, optionally DELAYED,
DELIVERED).
"""

from datetime import date, timedelta

from backend.app.core.data_labels import DataSourceLabel
from backend.app.data.config import GenerationConfig
from backend.app.data.generators.base import stream_rng
from backend.app.data.generators.suppliers import PROFILES


def _parse(value: str) -> date:
    return date.fromisoformat(value)


def generate_shipments(
    config: GenerationConfig,
    orders: list[dict[str, str | None]],
    supplier_profiles: dict[str, str],
) -> tuple[list[dict[str, str | None]], list[dict[str, str | None]]]:
    """Generate shipments and shipment events from purchase orders."""
    rng = stream_rng(config.seed, "shipments")
    shipments: list[dict[str, str | None]] = []
    events: list[dict[str, str | None]] = []
    end = config.end_date
    counter = 0
    for order in orders:
        order_date = _parse(str(order["order_date"]))
        expected = _parse(str(order["expected_delivery_date"]))
        profile = supplier_profiles.get(str(order["supplier_key"]), "RELIABLE")
        _, delay_mean, delay_sd, _, _ = PROFILES[profile]
        shipped = order_date + timedelta(days=rng.randint(0, 2))
        if shipped > expected:
            shipped = expected
        # Shipment count decision is deterministic per order.
        split = rng.random() < 0.12
        parts = 2 if split else 1
        for part in range(parts):
            counter += 1
            key = f"SH-{counter:06d}"
            delay = max(-2, int(round(rng.gauss(delay_mean, delay_sd))))
            actual = expected + timedelta(days=delay)
            if actual < shipped:
                actual = shipped
            if actual <= end:
                status = "delivered"
                actual_str: str | None = actual.isoformat()
            elif expected <= end:
                status = "delayed"
                actual_str = None
            else:
                status = "in_transit"
                actual_str = None
            shipments.append(
                {
                    "shipment_key": key,
                    "order_key": str(order["order_key"]),
                    "supplier_key": str(order["supplier_key"]),
                    "shipped_date": shipped.isoformat(),
                    "expected_arrival_date": expected.isoformat(),
                    "actual_arrival_date": actual_str,
                    "status": status,
                    "data_source_label": DataSourceLabel.SYNTHETIC.value,
                }
            )
            trail: list[tuple[str, str]] = [
                ("SHIPPED", shipped.isoformat()),
                ("IN_TRANSIT", (shipped + timedelta(days=1)).isoformat()),
            ]
            if delay > 3:
                trail.append(("DELAYED", expected.isoformat()))
            if actual_str is not None:
                trail.append(("DELIVERED", actual_str))
            for event_type, event_date in trail:
                if _parse(event_date) > end:
                    continue
                events.append(
                    {
                        "shipment_key": key,
                        "event_type": event_type,
                        "event_date": event_date,
                        "description": f"Synthetic {event_type.lower()} event for {key}.",
                    }
                )
        if split:
            order["status"] = "partially_received" if expected <= end else "ordered"
    return shipments, events
