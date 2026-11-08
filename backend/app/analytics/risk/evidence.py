"""Data/evidence risk domain (Phase 7).

Risk can be UNKNOWN because evidence is missing. This module turns
each missing-evidence item into an explicit UNKNOWN record so gaps
stay visible. Missing evidence is never converted into low risk.
"""

from backend.app.analytics.risk.types import RiskRecord, risk_id

DOMAIN = "evidence"


def assess_gaps(
    entity_type: str,
    entity_id: str,
    analysis_date: str,
    missing: list[str],
    product_id: str | None = None,
    warehouse_id: str | None = None,
    supplier_id: str | None = None,
) -> list[RiskRecord]:
    """Build one UNKNOWN record per missing-evidence item."""
    records: list[RiskRecord] = []
    for item in sorted(set(missing)):
        records.append(RiskRecord(
            risk_id=risk_id(DOMAIN, entity_type, f"{entity_id}:{item}", analysis_date),
            domain=DOMAIN, entity_type=entity_type, entity_id=entity_id,
            product_id=product_id, warehouse_id=warehouse_id, supplier_id=supplier_id,
            analysis_date=analysis_date, state="UNKNOWN", severity="UNKNOWN",
            evidence=[f"Missing evidence: {item}."],
            missing_evidence=[item],
            provenance={"data_source": "synthetic"},
            explanation=(
                f"Evidence risk is UNKNOWN: {item} is missing for {entity_id}. "
                "Missing evidence never implies low risk."
            ),
        ))
    return records
