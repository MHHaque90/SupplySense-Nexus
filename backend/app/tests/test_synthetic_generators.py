"""Phase 2 generator tests: determinism, realism rules, and edge cases."""

import pytest

from backend.app.data.config import GenerationConfig, build_config
from backend.app.data.generators import (
    bom,
    catalog,
    demand,
    disruptions,
    organizations,
    suppliers,
    users,
    warehouses,
)
from backend.app.data.generators.base import opening_balance
from backend.app.data.ingestion.pipeline import generate_dataset


def _small_config(**overrides) -> GenerationConfig:
    base = {"history_days": 30, "product_count": 8, "supplier_count": 4, "warehouse_count": 2}
    base.update(overrides)
    return build_config(**base)


def test_config_defaults_are_laptop_sized():
    config = GenerationConfig()
    assert config.history_days == 365
    assert config.product_count <= 100
    assert config.batch_size >= 100
    assert config.start_date < config.end_date


def test_organizations_are_synthetic():
    records = organizations.generate_organizations(GenerationConfig(organization_count=2))
    assert len(records) == 2
    assert all(r["data_source_label"] == "synthetic" for r in records)
    assert all("Nexus" in str(r["name"]) for r in records)


def test_users_use_safe_domain_and_test_passwords():
    config = GenerationConfig()
    records = users.generate_users(config, ["Nexus Retail Group"])
    assert len(records) == 5
    assert all(str(r["email"]).endswith("@supplysense.local") for r in records)
    assert all(str(r["password_hash"]).startswith("hashed:synthetic-test-only") for r in records)
    roles = {str(r["role"]) for r in records}
    assert {"admin", "analyst", "planner", "manager", "executive"} <= roles


def test_catalog_covers_profiles_and_tiers():
    config = _small_config(product_count=10)
    products = catalog.generate_products(config, ["Nexus Retail Group"], 10)
    assert len({p["sku"] for p in products}) == 10
    assert {str(p["demand_profile"]) for p in products} >= {"STABLE", "TRENDING", "SEASONAL"}
    assert {str(p["volume_tier"]) for p in products} >= {"high", "medium", "low"}
    assert all("NX-" in str(p["sku"]) for p in products)


def test_supplier_profiles_vary():
    config = _small_config()
    records = suppliers.generate_suppliers(config, ["Nexus Retail Group"], 5)
    assert len({str(r["supplier_profile"]) for r in records}) == 5


def test_first_component_is_single_sourced():
    config = _small_config(product_count=6, supplier_count=3)
    products = catalog.generate_products(config, ["Nexus Retail Group"], 6)
    sups = suppliers.generate_suppliers(config, ["Nexus Retail Group"], 3)
    links = suppliers.generate_supplier_products(config, products, sups)
    first_sku = str(products[0]["sku"])
    assert sum(1 for link in links if link["product_key"] == first_sku) == 1
    assert any(sum(1 for link in links if link["product_key"] == p["sku"]) > 1
               for p in products[1:])


def test_shared_components_exist():
    config = _small_config(product_count=12, supplier_count=4)
    products = catalog.generate_products(config, ["Nexus Retail Group"], 12)
    boms, components = bom.generate_bom(config, products)
    assert boms, "Expected finished products with BOMs"
    from collections import Counter
    usage = Counter(str(c["component_key"]) for c in components)
    assert max(usage.values()) > 1, "Expected shared components"


def test_bom_cycle_attempt_rejected():
    with pytest.raises(bom.BOMCycleError):
        bom.validate_no_cycles({"A": ["B"], "B": ["C"], "C": ["A"]})
    bom.validate_no_cycles({"A": ["B"], "B": ["C"], "C": []})


def test_demand_continuity_and_non_negative():
    config = _small_config()
    products = catalog.generate_products(config, ["Nexus Retail Group"], 4)
    whs = warehouses.generate_warehouses(config, ["Nexus Retail Group"], 2)
    rows = demand.generate_demand(config, products, whs)
    assert len(rows) == 4 * 2 * 30
    assert all(int(r["quantity"]) >= 0 for r in rows)
    assert all(r["data_source_label"] == "synthetic" for r in rows)


def test_intermittent_products_have_zero_days():
    config = _small_config(product_count=7)
    products = catalog.generate_products(config, ["Nexus Retail Group"], 7)
    intermittent = [p for p in products if p["demand_profile"] == "INTERMITTENT"]
    assert intermittent, "Expected an intermittent product"
    whs = warehouses.generate_warehouses(config, ["Nexus Retail Group"], 1)
    rows = demand.generate_demand(config, intermittent[:1], whs)
    assert any(int(r["quantity"]) == 0 for r in rows)


def test_zero_demand_product_generates_no_sales():
    from backend.app.data.generators import sales as sales_gen
    config = _small_config()
    demand_rows = [
        {"product_key": "NX-00001", "warehouse_key": "WH-NORTH", "date": "2026-01-01",
         "quantity": "0", "data_source_label": "synthetic"}
    ]
    products = [{"sku": "NX-00001", "unit_cost": "10.00", "organization_key": "O"}]
    orders, lines = sales_gen.generate_sales(config, demand_rows, products)
    assert orders == [] and lines == []


def test_disruptions_are_labeled_simulated():
    config = _small_config()
    products = catalog.generate_products(config, ["Nexus Retail Group"], 4)
    sups = suppliers.generate_suppliers(config, ["Nexus Retail Group"], 2)
    whs = warehouses.generate_warehouses(config, ["Nexus Retail Group"], 1)
    events, impacts = disruptions.generate_disruptions(config, sups, products, whs)
    assert len(events) == 5
    assert all(e["data_source_label"] == "simulated" for e in events)
    assert all(0.0 <= float(i["stockout_probability"]) <= 1.0 for i in impacts)
    for event in events:
        assert str(event["end_date"]) >= str(event["start_date"])


def test_opening_balance_policy():
    assert opening_balance(40.0, 21) == 840
    assert opening_balance(0.0, 21) == 1


def test_full_dataset_is_internally_consistent():
    dataset = generate_dataset(_small_config())
    counts = dataset.table_counts()
    assert counts["products"] == 8
    assert counts["demand_observations"] == 8 * 2 * 30
    assert counts["purchase_orders"] > 0
    assert counts["shipments"] >= counts["purchase_orders"]
    assert counts["disruptions"] == 5
