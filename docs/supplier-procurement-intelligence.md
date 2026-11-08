# Supplier & Procurement Intelligence: SupplySense Nexus (Phase 6)

**SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.** This analysis uses synthetic/simulated data and is not evidence about real suppliers, real procurement performance, or real business operations.

Phase 6 is DESCRIPTIVE intelligence only. It never ranks suppliers, never recommends suppliers or quantities, and never optimizes procurement. It answers: "Which supplier and procurement relationships are associated with inventory exposure, and what does the historical procurement data show?"

## 1. Objective

Connect Phase 5 inventory exposure with suppliers, supplier-product relationships, purchase orders, lines, shipments, events, and delivery history — transparently and without prescriptive conclusions.

## 2. Architecture

```
backend/app/analytics/procurement/
    types.py               ProcurementIntelligenceConfig + typed contracts
    supplier_performance.py  PO/shipment aggregation per supplier
    lead_times.py          Observed vs contracted lead times per relationship
    delivery.py            Delivery behavior + reliability classes
    supplier_product.py    Relationship metrics + warehouse-level exposure
    open_orders.py         Outstanding commitments, overdue, arrival status
    inbound.py             Inbound coverage states per series
    moq.py                 MOQ behavior (never EOQ)
    concentration.py       Shares, dependency classes, exposure linkage
    exposure.py            Supplier-linked Phase 5 exposure aggregation
    service_impact.py      Delay/service co-occurrence (no causality)
    risk_signals.py        Rule-based NO_SIGNAL/MONITOR/ELEVATED/HIGH_EXPOSURE/UNKNOWN
    reports.py             Per-supplier assembly + JSON/Markdown reporting
```

Phase 3 loaders (`procurement`, `suppliers`), Phase 5 intelligence contracts and builders, and Phase 4 forecast provenance are consumed; nothing upstream is modified.

## 3. Input Contracts

Suppliers and links from `datasets/suppliers.py`; PO lines and shipments from `datasets/procurement.py`; Phase 5 `InventoryIntelligenceResult` objects (position, forecast, coverage, stockout, health, reorder, uncertainty, service). No new extraction paths; column-only reads; point-in-time filtering (≤ analysis date) throughout.

## 4. Supplier Metrics

Per supplier: PO/line counts, ordered quantity, received quantity (inferred from delivered shipments linked to the PO — documented assumption; per-line partials not represented), shipment/completed/on-time/late counts and rates, delay avg/median/max, lead-time avg/median/min/max/std. Missing evidence stays explicit (None + missing_evidence list).

## 5. Procurement Metrics

Per PO line: ordered/received/remaining quantities, expected arrival, overdue flag (expected < analysis date with remaining > 0), days outstanding, arrival status (expected/overdue/received/unknown). Open = `ordered` or `partially_received` statuses.

## 6. Lead-Time Methodology

Observed lead time = actual arrival − PO order date over delivered shipments only. Contracted terms come from supplier-product links. Percentiles (p25/p50/p75/p90) only with ≥3 observations. Delay frequency uses the configured grace. Observed history is described; no lead-time forecasting model is implemented.

## 7. Delivery Methodology

On-time = delay ≤ grace days over delivered shipments. Reliability classes with fixed rule order: UNKNOWN (< min_shipments) → STABLE (no lateness) → HIGH_DELAY (late rate ≥ high cutoff) → DELAYED (≥ delayed cutoff) → VARIABLE (spread ≥ cutoff) → DELAYED otherwise. Every outcome carries evidence text.

## 8. Supplier-Product Methodology

Per relationship: PO/ordered/received/shipment counts, observed lead time, on-time rate, MOQ + compliance, plus warehouse lists for exposure (all/at-risk/stockout) and high-uncertainty flags joined through product → warehouse → Phase 5 results.

## 9. Open PO Methodology

Outstanding states, inferred received quantities, overdue detection, earliest-expected-arrival allocation per PO/product for inbound mapping.

## 10. Inbound Methodology

Known inbound = remaining quantities of open lines expected inside the window. States vs uncovered horizon demand: INBOUND_SUPPORTED (no shortfall or inbound covers it), INBOUND_PARTIAL (reserved for partial-receipt evidence), INBOUND_INSUFFICIENT, NO_KNOWN_INBOUND, UNKNOWN. No certainty claimed when arrival data is missing; no expediting/cancellation language.

## 11. MOQ Methodology

MOQ, order counts, compliance rate, below-MOQ counts, min/median order-to-MOQ ratios per supplier (and per relationship). No EOQ, no optimal quantities, no batch advice.

## 12. Concentration Methodology

Spend/quantity/PO-count shares, suppliers-per-product counts, SINGLE/MULTI/NO_HISTORY dependency classes, category top-share, and exposed-series linkage shares. Concentration is an exposure metric; never a diversification order.

## 13. Inventory Exposure Methodology

Supplier → links → products → warehouses → Phase 5 results: affected products/warehouses, at-risk, stocked-out, urgent-signal, and high-uncertainty product lists, plus open PO and inbound quantities. Traceability (product, warehouse, analysis date, model, version, confidence, health) preserved from Phase 5 objects.

## 14. Risk Signals

Evidence flags (exposure, overdue inbound, delays, variability, single-supplier dependency, concentration, uncertainty, insufficient evidence) combine by fixed ladder into NO_SIGNAL/MONITOR/ELEVATED/HIGH_EXPOSURE/UNKNOWN. Every signal carries reason, evidence list, metrics, and missing evidence. No aggregate score, no ranking.

## 15. Point-in-Time Rules

For analysis date T, no record after T influences results: POs by order date, shipments by actual arrival, expected arrivals only as future expectations for open/inbound views, service co-occurrence within a trailing window ending at T. Leakage-tested with future-record injection.

## 16. Synthetic-Data Rules

Every report carries the synthetic disclaimer; every result has `synthetic: true`; wording bans ("best/worst/preferred/recommended supplier", "should be replaced", "switch", order quantities, "diversify") are test-enforced. Received-quantity inference and partial-fulfillment limits are documented assumptions, not hidden repairs.

## 17. Limitations

- Received quantities inferred at PO granularity; per-line partials not represented.
- Reliability classes need ≥5 delivered shipments; thin histories stay UNKNOWN.
- Current synthetic data yields mostly ELEVATED/HIGH_DELAY suppliers by design of generator delay profiles — descriptive of the dataset, not of any real supplier.
- No historical backtesting of signals; no causal claims anywhere.

## 18. Examples

```bash
python scripts/analyze_supply_chain.py procurement-intelligence \
  --supplier-id <uuid> --forecast-horizon 28 \
  --include-exposure --include-concentration \
  --output-json procurement.json --output-markdown procurement.md
```

## 19. Phase 7 Handoff

Phase 7 (Supply-Chain Risk Intelligence) can consume per supplier: performance, delivery reliability class, lead-time variability, concentration shares, single-source dependencies, open/inbound exposure, inventory/stockout/service exposure, and procurement risk signals — plus per-relationship MOQ, lead-time, and exposure detail. Suggested: join `procurement-intelligence` JSON output to BOM/component graphs by product for propagation analysis; no schema change needed.
