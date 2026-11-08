"""Phase 5 report assembly tests (JSON, Markdown, labeling)."""

from datetime import date

from backend.app.analytics.inventory import reports
from backend.app.analytics.inventory.types import (
    DEFAULT_INVENTORY_CONFIG,
    InventoryHealth,
    InventoryIntelligenceResult,
    InventoryPosition,
)

ANALYSIS = date(2026, 6, 30)


def _result(product="P1", health="HEALTHY"):
    return InventoryIntelligenceResult(
        product_id=product,
        warehouse_id="W1",
        analysis_date="2026-06-30",
        position=InventoryPosition(
            product_id=product, warehouse_id="W1", analysis_date="2026-06-30",
            current_on_hand=100.0, latest_snapshot_date="2026-06-30",
        ),
        health=InventoryHealth(
            product_id=product, warehouse_id="W1", health=health, reason="test reason"
        ),
    )


def test_report_summary_counts():
    results = [_result("P1", "HEALTHY"), _result("P2", "CRITICAL"), _result("P3", "UNKNOWN")]
    summary = reports.summarize(results)
    assert summary["series"] == 3
    assert summary["health"] == {"HEALTHY": 1, "CRITICAL": 1, "UNKNOWN": 1}


def test_report_json_structure_and_labeling():
    report = reports.build_report(
        [_result()], [], [{"product_id": "P1", "warehouse_id": "W1",
                           "turnover_proxy": 2.0, "sales": 100.0, "average_inventory": 50.0}],
        [{"product_id": "P1", "warehouse_id": "W1", "days_since_movement": 1,
          "days_since_receipt": 5, "note": "n"}],
        {"by_warehouse": [], "by_product": []},
        ANALYSIS, 28, DEFAULT_INVENTORY_CONFIG,
    )
    assert report["synthetic"] is True
    assert "SYNTHETIC DATA" in report["disclaimer"]
    assert report["forecast_horizon_days"] == 28
    assert report["analysis_date"] == "2026-06-30"
    assert report["config"]["critical_dos"] == 3.0
    assert len(report["limitations"]) >= 5
    assert all(result["synthetic"] is True for result in report["results"])


def test_markdown_wording_and_sections():
    report = reports.build_report(
        [_result("P1", "AT_RISK")], [], [], [], {"by_warehouse": [], "by_product": []},
        ANALYSIS, 14, DEFAULT_INVENTORY_CONFIG,
    )
    markdown = reports.render_markdown(report)
    assert markdown.startswith("# SupplySense Nexus Inventory Intelligence Report")
    assert "SYNTHETIC DATA" in markdown
    for section in ("position summary", "Coverage summary", "Days-of-supply",
                    "Projected stockout", "health summary", "Reorder signal",
                    "uncertainty", "Service-level", "Turnover", "Aging",
                    "Anomaly summary", "breakdown", "limitations"):
        assert section in markdown
    for banned in ("order 50 units", "you should buy", "optimal order", "guaranteed returns"):
        assert banned not in markdown.lower()
