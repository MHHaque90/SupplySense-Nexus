"""Centralized configuration for synthetic data generation (Phase 2)."""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class GenerationConfig:
    """Typed configuration for the synthetic ERP data generator.

    All generation parameters live here so scale, seed, and policy
    constants are not hard-coded throughout the generator modules.
    """

    seed: int = 42
    organization_count: int = 1
    product_count: int = 24
    supplier_count: int = 8
    warehouse_count: int = 3
    history_days: int = 365
    end_date: date = date(2026, 6, 30)
    average_daily_demand: float = 40.0
    scenario_scale: float = 1.0
    batch_size: int = 500
    generator_version: str = "2.0.0"
    # Baseline replenishment policy used ONLY for data generation.
    # This is not an optimized procurement policy.
    coverage_days: int = 21
    order_up_to_days: int = 45
    reorder_service_factor: float = 1.2

    @property
    def start_date(self) -> date:
        """First day of the generated history (inclusive)."""
        return self.end_date - timedelta(days=self.history_days - 1)

    def per_organization_counts(self) -> dict[str, int]:
        """Split entity counts across organizations for tenant isolation."""
        orgs = max(1, self.organization_count)
        return {
            "products": max(4, self.product_count // orgs),
            "suppliers": max(2, self.supplier_count // orgs),
            "warehouses": max(1, self.warehouse_count // orgs),
        }

    def to_dict(self) -> dict[str, str | int | float]:
        """Return a JSON-serializable view of the configuration."""
        return {
            "seed": self.seed,
            "organization_count": self.organization_count,
            "product_count": self.product_count,
            "supplier_count": self.supplier_count,
            "warehouse_count": self.warehouse_count,
            "history_days": self.history_days,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "average_daily_demand": self.average_daily_demand,
            "scenario_scale": self.scenario_scale,
            "batch_size": self.batch_size,
            "generator_version": self.generator_version,
        }


DEFAULT_CONFIG: GenerationConfig = GenerationConfig()


def build_config(**overrides: int | float | str | date) -> GenerationConfig:
    """Build a :class:`GenerationConfig` with selective overrides."""
    base: dict[str, int | float | str | date] = {
        "seed": DEFAULT_CONFIG.seed,
        "organization_count": DEFAULT_CONFIG.organization_count,
        "product_count": DEFAULT_CONFIG.product_count,
        "supplier_count": DEFAULT_CONFIG.supplier_count,
        "warehouse_count": DEFAULT_CONFIG.warehouse_count,
        "history_days": DEFAULT_CONFIG.history_days,
        "end_date": DEFAULT_CONFIG.end_date,
        "average_daily_demand": DEFAULT_CONFIG.average_daily_demand,
        "scenario_scale": DEFAULT_CONFIG.scenario_scale,
        "batch_size": DEFAULT_CONFIG.batch_size,
        "generator_version": DEFAULT_CONFIG.generator_version,
    }
    base.update(overrides)
    return GenerationConfig(**base)  # type: ignore[arg-type]
