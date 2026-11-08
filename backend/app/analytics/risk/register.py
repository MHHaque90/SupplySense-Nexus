"""Structured risk register with filters (Phase 7)."""

from backend.app.analytics.risk.types import RiskRecord


def filter_records(
    records: list[RiskRecord],
    severity: str | None = None,
    domain: str | None = None,
    supplier_id: str | None = None,
    product_id: str | None = None,
    warehouse_id: str | None = None,
    state: str | None = None,
    include_unknown: bool = True,
) -> list[RiskRecord]:
    """Filter the register by severity, domain, entity, or state."""
    selected: list[RiskRecord] = []
    for record in records:
        if not include_unknown and record.severity == "UNKNOWN":
            continue
        if severity is not None and record.severity != severity:
            continue
        if domain is not None and record.domain != domain:
            continue
        if supplier_id is not None and record.supplier_id != supplier_id:
            continue
        if product_id is not None and record.product_id != product_id:
            continue
        if warehouse_id is not None and record.warehouse_id != warehouse_id:
            continue
        if state is not None and record.state != state:
            continue
        selected.append(record)
    return selected


def to_dict_list(records: list[RiskRecord]) -> list[dict]:
    """Serialize register records for reports."""
    return [record.to_dict() for record in records]
