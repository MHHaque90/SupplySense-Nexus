"""Inventory aging via recorded movement (Phase 5).

Lot-level age does not exist in the schema, so this module reports
"days since last recorded movement" and stagnant durations — never
"inventory age".
"""

import pandas as pd


def days_since_movement(
    product_id: str,
    warehouse_id: str,
    transactions: pd.DataFrame,
    analysis_date: object,
) -> dict[str, object]:
    """Report days since last movement and last receipt per series."""
    series = transactions[
        (transactions["product_id"] == product_id)
        & (transactions["warehouse_id"] == warehouse_id)
    ]
    reference = pd.to_datetime(analysis_date).date()
    if series.empty:
        return {
            "days_since_movement": None,
            "days_since_receipt": None,
            "note": "No transaction history; movement unknown.",
        }
    dates = pd.to_datetime(series["timestamp"]).dt.date
    last_movement = dates.max()
    receipts = series[series["transaction_type"] == "RECEIPT"]
    last_receipt = (
        pd.to_datetime(receipts["timestamp"]).dt.date.max() if not receipts.empty else None
    )
    return {
        "days_since_movement": (reference - last_movement).days,
        "days_since_receipt": (reference - last_receipt).days if last_receipt else None,
        "note": "Days since last recorded movement, not lot age.",
    }
