"""Rule-based inventory anomaly detection (Phase 5).

Deterministic rules only; no ML, no registry. Every anomaly carries
product, warehouse, date, observed and reference values, rule,
severity, and explanation.
"""

import pandas as pd

from backend.app.analytics.inventory.types import InventoryAnomaly, InventoryIntelligenceConfig


def detect_anomalies(
    product_id: str,
    warehouse_id: str,
    snapshots: pd.DataFrame,
    transactions: pd.DataFrame,
    analysis_date: object,
    config: InventoryIntelligenceConfig,
) -> list[InventoryAnomaly]:
    """Apply descriptive anomaly rules to one series."""
    anomalies: list[InventoryAnomaly] = []
    reference = pd.to_datetime(analysis_date).date()
    series_snaps = snapshots[
        (snapshots["product_id"] == product_id)
        & (snapshots["warehouse_id"] == warehouse_id)
        & (pd.to_datetime(snapshots["snapshot_date"]).dt.date <= reference)
    ].sort_values("snapshot_date")
    series_txns = transactions[
        (transactions["product_id"] == product_id)
        & (transactions["warehouse_id"] == warehouse_id)
        & (pd.to_datetime(transactions["timestamp"]).dt.date <= reference)
    ]
    values = series_snaps["on_hand"].astype(float).tolist()
    dates = [str(d) for d in series_snaps["snapshot_date"].tolist()]
    for position in range(1, len(values)):
        previous, current = values[position - 1], values[position]
        if previous > 0 and (previous - current) / previous >= config.anomaly_drop_ratio and current >= 0:
            anomalies.append(InventoryAnomaly(
                product_id=product_id, warehouse_id=warehouse_id, date=dates[position],
                observed=current, reference=previous,
                rule="sudden_drop",
                severity="high" if current == 0 else "watch",
                explanation=(
                    f"On-hand fell from {previous:.0f} to {current:.0f} "
                    f"(drop >= {config.anomaly_drop_ratio:.0%}) in observed records."
                ),
            ))
        if current < 0:
            anomalies.append(InventoryAnomaly(
                product_id=product_id, warehouse_id=warehouse_id, date=dates[position],
                observed=current, reference=0.0, rule="negative_inventory",
                severity="high",
                explanation="Negative on-hand is impossible in normal operations.",
            ))
    for _, row in series_txns.iterrows():
        if str(row["transaction_type"]) == "ADJUSTMENT" and float(row["quantity"]) >= config.anomaly_adjustment_qty:
            anomalies.append(InventoryAnomaly(
                product_id=product_id, warehouse_id=warehouse_id, date=str(row["timestamp"]),
                observed=float(row["quantity"]), reference=None, rule="large_adjustment",
                severity="watch",
                explanation=(
                    f"Adjustment of {float(row['quantity']):.0f} meets the "
                    f"{config.anomaly_adjustment_qty:.0f} review threshold."
                ),
            ))
    if not series_txns.empty:
        last_move = pd.to_datetime(series_txns["timestamp"]).dt.date.max()
        stagnant = (reference - last_move).days
        if stagnant >= config.stagnant_days:
            anomalies.append(InventoryAnomaly(
                product_id=product_id, warehouse_id=warehouse_id, date=str(reference),
                observed=float(stagnant), reference=float(config.stagnant_days),
                rule="no_movement", severity="watch",
                explanation=(
                    f"No recorded movement for {stagnant} days "
                    f"(threshold {config.stagnant_days})."
                ),
            ))
    return anomalies
