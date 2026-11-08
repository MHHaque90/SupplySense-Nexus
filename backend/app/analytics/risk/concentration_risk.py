"""Concentration risk domain (Phase 7).

Consumes Phase 6 concentration analytics. Concentration is exposure,
never a diversification order.
"""

from backend.app.analytics.procurement.types import SupplierConcentration
from backend.app.analytics.risk.types import (
    RiskIntelligenceConfig,
    RiskRecord,
    max_severity,
    risk_id,
)

DOMAIN = "concentration"


def assess(
    rows: list[SupplierConcentration],
    analysis_date: str,
    config: RiskIntelligenceConfig,
) -> list[RiskRecord]:
    """Assess concentration risk from share rows."""
    records: list[RiskRecord] = []
    for row in rows:
        if row.share is None:
            records.append(RiskRecord(
                risk_id=risk_id(DOMAIN, "concentration",
                                f"{row.dimension}:{row.supplier_id}", analysis_date),
                domain=DOMAIN, entity_type="concentration",
                entity_id=f"{row.dimension}:{row.supplier_id}",
                supplier_id=row.supplier_id, analysis_date=analysis_date,
                state="UNKNOWN", severity="UNKNOWN",
                evidence=["Share could not be computed."],
                missing_evidence=["concentration_basis"],
                provenance={"data_source": "synthetic"},
                explanation="Concentration risk is UNKNOWN without a computable share.",
            ))
            continue
        if row.share >= 0.7:
            state = "HIGH"
        elif row.share >= config.concentrated_share:
            state = "MODERATE"
        else:
            state = "LOW"
        records.append(RiskRecord(
            risk_id=risk_id(DOMAIN, "concentration",
                            f"{row.dimension}:{row.supplier_id}", analysis_date),
            domain=DOMAIN, entity_type="concentration",
            entity_id=f"{row.dimension}:{row.supplier_id}",
            supplier_id=row.supplier_id, analysis_date=analysis_date,
            state=state, severity=state,
            evidence=[f"Share is {row.share:.2f} on basis {row.basis}. {row.note}"],
            metrics={"share": row.share},
            provenance={"data_source": "synthetic"},
            explanation=f"Concentration exposure is {state.lower()} for {row.dimension}.",
        ))
    if not records:
        records.append(RiskRecord(
            risk_id=risk_id(DOMAIN, "concentration", "none", analysis_date),
            domain=DOMAIN, entity_type="concentration", entity_id="none",
            analysis_date=analysis_date, state="UNKNOWN", severity="UNKNOWN",
            evidence=["No concentration rows available."],
            missing_evidence=["concentration_rows"],
            provenance={"data_source": "synthetic"},
            explanation="Concentration risk is UNKNOWN for lack of rows.",
        ))
    return records


def highest(records: list[RiskRecord]) -> str:
    """Return the highest concentration state present."""
    return max_severity([record.severity for record in records])
