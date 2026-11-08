"""Inventory health classification (Phase 5).

Transparent rule order with reasons; missing evidence is reported,
never silently defaulted. Thresholds come from configuration.
"""

from backend.app.analytics.inventory.types import (
    CoverageResult,
    ForecastInput,
    InventoryHealth,
    InventoryIntelligenceConfig,
    InventoryPosition,
    StockoutExposure,
)


def classify_health(
    position: InventoryPosition,
    forecast: ForecastInput | None,
    coverage: CoverageResult | None,
    stockout: StockoutExposure | None,
    config: InventoryIntelligenceConfig,
    service_warning: bool = False,
) -> InventoryHealth:
    """Classify one series as STOCKOUT/CRITICAL/AT_RISK/HEALTHY/EXCESS/UNKNOWN."""
    key = (position.product_id, position.warehouse_id)
    missing: list[str] = []
    if position.unknown or position.current_on_hand is None:
        return InventoryHealth(
            product_id=key[0], warehouse_id=key[1], health="UNKNOWN",
            reason="No inventory position is known at the analysis date.",
            missing_evidence=["inventory_position"],
        )
    if forecast is None or forecast.missing:
        missing.append("forecast")
    on_hand = position.current_on_hand
    if on_hand <= 0:
        return InventoryHealth(
            product_id=key[0], warehouse_id=key[1], health="STOCKOUT",
            reason=f"Current on-hand is {on_hand:.0f}; the series is stocked out.",
            missing_evidence=missing,
        )
    dos = coverage.forecast_days_of_supply if coverage else None
    dos_state = coverage.forecast_days_of_supply_state if coverage else "unknown"
    ratio = coverage.coverage_ratio_point if coverage else None
    if stockout is not None and stockout.exposure in ("immediate", "elevated"):
        return InventoryHealth(
            product_id=key[0], warehouse_id=key[1], health="CRITICAL",
            reason=(
                f"Projected stockout in {stockout.days_until_stockout} days "
                f"({stockout.projected_stockout_date}); exposure is {stockout.exposure}."
            ),
            missing_evidence=missing,
        )
    if (
        dos is not None and dos >= config.excess_dos
    ) or (
        ratio is not None and ratio >= config.excess_coverage_ratio
    ):
        detail = (
            f"days of supply {dos:.1f}" if dos is not None and dos >= config.excess_dos
            else f"coverage ratio {ratio:.2f}"
        )
        return InventoryHealth(
            product_id=key[0], warehouse_id=key[1], health="EXCESS",
            reason=(
                f"Excess-inventory signal: {detail} with low near-term demand. "
                "Descriptive only; no reduction action is recommended."
            ),
            missing_evidence=missing,
        )
    if stockout is not None and stockout.exposure == "watch":
        return InventoryHealth(
            product_id=key[0], warehouse_id=key[1], health="AT_RISK",
            reason=(
                f"AT_RISK because point forecast reaches zero inventory within "
                f"{stockout.days_until_stockout} days."
            ),
            missing_evidence=missing,
        )
    if dos_state == "unbounded":
        return InventoryHealth(
            product_id=key[0], warehouse_id=key[1], health="HEALTHY",
            reason="Zero expected demand with stock on hand; coverage is unbounded.",
            missing_evidence=missing,
        )
    if dos is not None and dos <= config.critical_dos:
        return InventoryHealth(
            product_id=key[0], warehouse_id=key[1], health="CRITICAL",
            reason=f"Days of supply {dos:.1f} is at or below the critical threshold.",
            missing_evidence=missing,
        )
    if dos is not None and dos <= config.at_risk_dos:
        return InventoryHealth(
            product_id=key[0], warehouse_id=key[1], health="AT_RISK",
            reason=f"Days of supply {dos:.1f} is below the at-risk threshold.",
            missing_evidence=missing,
        )
    if service_warning:
        return InventoryHealth(
            product_id=key[0], warehouse_id=key[1], health="AT_RISK",
            reason="Inventory looks adequate but repeated recent stockouts require attention.",
            missing_evidence=missing,
        )
    if dos is None and ratio is None:
        return InventoryHealth(
            product_id=key[0], warehouse_id=key[1], health="UNKNOWN",
            reason="Coverage cannot be computed without a forecast.",
            missing_evidence=missing or ["forecast"],
        )
    return InventoryHealth(
        product_id=key[0], warehouse_id=key[1], health="HEALTHY",
        reason="Adequate coverage with no projected stockout in the horizon.",
        missing_evidence=missing,
    )
