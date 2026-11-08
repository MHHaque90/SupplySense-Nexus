# Supply-Chain Risk Intelligence: SupplySense Nexus (Phase 7)

**SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.** This analysis uses synthetic/simulated data and is not evidence about real suppliers, real procurement performance, real supply-chain risk, or real business operations.

Phase 7 is RISK IDENTIFICATION + AGGREGATION + EXPLANATION + TRACEABILITY + MONITORING SIGNALS. It never optimizes, simulates disruption, replays decisions, or automates decisions.

## 1. Objective

Transform Phase 5 inventory and Phase 6 procurement intelligence into a transparent risk layer answering: "Where are the material dependencies and exposures, what evidence supports them, how severe are they, and what evidence is missing?"

## 2. Architecture

```
backend/app/analytics/risk/
    types.py               RiskIntelligenceConfig + RiskRecord + severity orders
    inventory_risk.py      Phase 5 health/DOS/urgency/volatility mapping
    supplier_risk.py       Phase 6 delivery/exposure bands (no rankings)
    procurement_risk.py    Open/overdue/delay/MOQ evidence
    dependency.py          Product, supplier-fanout, warehouse breadth
    service_risk.py        Stockouts, warnings, delay associations (no causality)
    concentration_risk.py  Share-band exposure
    leadtime_risk.py       Observed lead-time evidence + sample sufficiency
    uncertainty_risk.py    Interval spread + validation support
    inbound_risk.py        Inbound coverage states
    evidence.py            Missing-evidence UNKNOWN records
    aggregation.py         Series + supplier overall exposure with boosts
    risk_explanations.py   Templated explanations
    register.py            Filterable register (severity/domain/supplier/...)
    reports.py             Assembly + JSON/Markdown reporting
```

Phase 4 forecasting, Phase 5 inventory, and Phase 6 procurement files are untouched; only public interfaces are consumed.

## 3. Risk Domains

Inventory, supplier, procurement, dependency, service, concentration, lead-time, forecast uncertainty, inbound exposure, and data/evidence. Domains stay separate until transparent aggregation; no opaque single score exists.

## 4. Input Contracts

Phase 5 `InventoryIntelligenceResult` objects (position, forecast, coverage, stockout, health, reorder, uncertainty, service) and Phase 6 `ProcurementIntelligenceResult` objects (performance, delivery, relationships, open orders, MOQ, exposure, risk signals, service impacts), plus Phase 3 loader frames. Column-only reads; point-in-time filtering (≤ analysis date) throughout.

## 5. Evidence Model

Every `RiskRecord`: risk_id (`domain:entity:date`, deterministic), domain, entity type/id, product/warehouse/supplier ids, analysis date, state, severity, evidence list, metrics, supporting record refs, missing evidence, confidence, provenance (model, version, origin, horizon, validation, health, data_source), explanation, synthetic flag.

## 6. Risk Rules

- Inventory: health mapping (STOCKOUT→CRITICAL … HEALTHY/EXCESS→LOW) layered with DOS bands, reorder urgency, volatility, and stockout history; max-severity wins.
- Supplier: late-rate bands, lead-time variability, linked stockout/at-risk exposure; insufficient shipments → UNKNOWN.
- Procurement: overdue lines, delay evidence, MOQ compliance; empty open evidence → UNKNOWN.
- Dependency: single-supplier HIGH, multi LOW, no history UNKNOWN; fanout by exposed share; warehouse breadth by supplier count.
- Service: repeated stockouts, affirmed warnings, delay associations (association-only language).
- Concentration: share ≥0.7 HIGH, ≥0.5 MODERATE, else LOW; uncomputable → UNKNOWN.
- Lead-time: delay-frequency bands + variability; <5 observations → UNKNOWN.
- Uncertainty: interval-spread bands + validation-support gating; missing forecast → UNKNOWN.
- Inbound: coverage-state mapping; unknown coverage → UNKNOWN.
- Evidence: every missing item becomes an explicit UNKNOWN record; missing never implies LOW.

## 7. Severity Rules

Exposure ladder UNKNOWN/LOW/MODERATE/HIGH/CRITICAL with max-severity ordering; supplier ladder keeps Phase 6 vocabulary (UNKNOWN/LOW/MODERATE/ELEVATED/HIGH); procurement keeps Phase 6 vocabulary. Overall aggregation uses max severity plus two documented combination boosts (HIGH inventory + SINGLE dependency + HIGH lead-time variability; PROJECTED STOCKOUT + shortfall inbound + HIGH supplier delays), each naming its evidence. Deterministic; no weights.

## 8. Dependency Methodology

Structural exposure from observed relationships: per-product supplier counts, per-supplier exposed-product shares, per-warehouse serving-supplier sets derived from stocked products. Dependency is exposure; diversification is never recommended.

## 9. Supplier Risk Methodology

Late-rate bands, lead-time variability, observation counts, and linked inventory exposure from Phase 6 outputs. Descriptive bands, never best/worst labels.

## 10. Inventory Risk Methodology

Phase 5 health mapping plus DOS bands, reorder urgency, volatility, and stockout history. Broader interpretation layered alongside health, never replacing it.

## 11. Service Risk Methodology

Repeated stockouts, affirmed service warnings (negated text excluded), and delay-during-exposure associations. Association-only templates; causality never claimed.

## 12. Uncertainty Methodology

Interval spread and validation-support bands over consumed Phase 4 intervals; bounds never treated as guaranteed worst/best cases. Intervals are never recomputed.

## 13. Evidence/UNKNOWN Handling

Missing position, forecast, delivery history, open procurement, lead-time history, and coverage each produce explicit UNKNOWN records. The register filter can include or exclude UNKNOWN; reports list missing evidence per record and in aggregate.

## 14. Point-in-Time Rules

For analysis date T, no record after T influences results: inventory, demand, forecasts, suppliers, relationships, POs, shipments, events, delivery and service history. Leakage-tested with future-record injection across all loaders and domains.

## 15. Synthetic-Data Rules

Every report carries the disclaimer; every record has `synthetic: true`; wording bans (supplier/procurement recommendations, optimization, disruption predictions, Replay decisions, best/worst rankings) are test-enforced. Provenance preserves model, version, origin, horizon, validation, and health.

## 16. Limitations

- Current synthetic data yields mostly ELEVATED/HIGH_DELAY suppliers and thin per-relationship lead-time histories (many UNKNOWN lead-time records) — descriptive of the dataset.
- No live STOCKOUT series in the current data; those paths are unit-tested.
- No historical backtesting; analysis is current/future at the analysis date.
- Received quantities inherit Phase 6 inference limits.

## 17. Examples

```bash
python scripts/analyze_supply_chain.py risk-intelligence \
  --forecast-horizon 28 --severity HIGH --output-json risk.json

python scripts/analyze_supply_chain.py risk-intelligence \
  --supplier-id <uuid> --domain supplier --include-evidence \
  --output-markdown risk.md
```

## 18. Phase 8 Handoff

Phase 8 (Disruption Simulation) can consume: the filterable risk register, supplier dependencies and fan-out, inventory and supplier exposure, lead-time variability, open inbound exposure, projected stockout exposure, service exposure, concentration shares, uncertainty bands, and affected product/warehouse relationships — all with provenance and deterministic IDs. Documented interface only; no simulation implemented.
