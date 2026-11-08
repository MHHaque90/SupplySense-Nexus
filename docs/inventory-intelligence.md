# Inventory Intelligence: SupplySense Nexus (Phase 5)

**Phase 5 is inventory intelligence. Safety-stock optimization is NOT implemented. Inventory optimization is NOT implemented.**

All analytics operate on SYNTHETIC data with analytical wording only ("synthetic dataset", "observed generated records", "analytical signal").

## 1. Inventory Intelligence Architecture

```
backend/app/analytics/inventory/
    types.py            InventoryIntelligenceConfig + typed contracts
    position.py         Point-in-time positions (analysis-date discipline)
    forecast_inputs.py  Persisted-first forecast loading + public-interface fallback
    coverage.py         Forecast vs historical days of supply, coverage ratios
    projection.py       Daily trajectories + known-inbound mapping
    stockout.py         Exposure categories (no_exposure/watch/elevated/immediate/unknown)
    health.py           STOCKOUT/CRITICAL/AT_RISK/HEALTHY/EXCESS/UNKNOWN + reasons
    reorder_signals.py  Threshold SIGNALS + urgency (no_signal/monitor/plan/urgent/unknown)
    uncertainty.py      Interval-case exposure notes (consumes Phase 4 bounds)
    service.py          Repeated-stockout warnings (no supplier causality)
    turnover.py         Per-series turnover proxy/trend + concentration helpers
    aging.py            Days-since-movement (never "lot age")
    anomalies.py        Rule-based anomalies with evidence
    concentration.py    Warehouse/product unit shares (descriptive)
    reports.py          Result assembly + JSON/Markdown reporting
```

Phase 3 loaders/KPIs and Phase 4 selection/forecasting/persistence contracts are consumed, never reimplemented. No Phase 4 file was modified.

## 2. Phase 4 Forecast Inputs

Per series: point/lower/upper, horizon, dates, model name/version/family, demand profile, validation metric/score/folds, explanation, confidence, assumptions, warnings, plus source flag (`persisted` vs `generated_for_analysis`). Persisted rows group by product/warehouse/model-version with latest origin winning; missing series fall back to the public `evaluate_dataset` interface; total failure yields explicit MISSING_FORECAST (never fabricated).

## 3. Inventory Position

Latest snapshot on or before the analysis date plus 30-day recent statistics, signed movement, adjustment counts, and stockout observations. Warehouses never combined; future rows cannot leak (tested).

## 4. Coverage

`forecast_days_of_supply` from selected-forecast daily demand with states finite/unbounded (zero demand with stock)/unknown (missing forecast); `historical_days_of_supply` labeled separately; coverage ratios under lower/point/upper demand cases (higher demand → lower coverage, labeled per case).

## 5. Days of Supply

Forecast-based DOS is primary; historical DOS is a separate labeled field. Never substituted silently.

## 6. Projection

`projected[t+1] = projected[t] − forecast[t] + known_inbound[t]`. Known inbound comes only from undelivered shipments expected inside the window, allocated by PO-line quantity with one contribution per open PO/product at its earliest in-window arrival (split-shipment partials not represented). Otherwise demand-only with a documented assumption. No future POs, no simulated procurement.

## 7. Stockout Exposure

First trajectory date at or below zero defines the projected stockout date and days-until. Categories: `immediate` (current stockout), `elevated` (≤ urgent_days), `watch` (later in horizon), `no_exposure`, `unknown`. Demand remaining at stockout recorded.

## 8. Health Classification

Rule order: STOCKOUT (on-hand ≤ 0) → CRITICAL (elevated/immediate exposure) → EXCESS (DOS ≥ 60 or coverage ratio ≥ 2) → AT_RISK (watch exposure) → HEALTHY unbounded → CRITICAL (DOS ≤ 3) → AT_RISK (DOS ≤ 7) → AT_RISK (service warning) → UNKNOWN (no coverage) → HEALTHY. Every outcome carries a reason; missing evidence listed. EXCESS is descriptive only.

## 9. Reorder Signals

Threshold = expected demand over `coverage_period_days` + informational buffer (`uncertainty_buffer_factor` × mean interval width — derived from forecast uncertainty, not an optimized safety stock). Urgency: no_signal / monitor / plan (≤ plan_days) / urgent (≤ urgent_days or critical DOS) / unknown. Output is threshold, inventory, status, reason — never quantities, suppliers, or timing.

## 10. Forecast Uncertainty

Intervals consumed from Phase 4, never recomputed. Notes report point/lower/upper horizon totals, level, mean width, and spread with "upper forecast-bound scenario" language (never worst-case guarantees).

## 11. Service-Level Signals

Repeated recent stockouts (≥ 2 in 30 days) raise a warning that can lift an otherwise adequate position to AT_RISK. No supplier causality inferred.

## 12. Turnover

Per-series unit turnover proxy (sales / mean on-hand) plus early/recent split trend. Quantity-based; no monetary valuation (schema limitation documented since Phase 3).

## 13. Aging

Days since last recorded movement and since last receipt. Called movement age, never lot age.

## 14. Anomaly Detection

Rules: ≥50% week-over-week snapshot drop, negative on-hand (high), adjustments ≥100 units, ≥45 days without movement. Each anomaly carries product, warehouse, date, observed/reference values, rule, severity, and explanation. Note: weekly snapshot cadence means large week-over-week moves are common in generated data; rules are intentionally simple and review-oriented.

## 15. Threshold Configuration

All thresholds live in `InventoryIntelligenceConfig` (see `types.py` docstring for each definition) and are echoed in every report under `config`.

## 16. Synthetic-Data Limitations

- Current dev data has no stocked-out series; STOCKOUT/CRITICAL paths validated by unit tests.
- Historical backtesting not implemented (persisted forecast history insufficient).
- Lost-sales generation means fulfilled demand ≤ requested demand.
- Anomaly rules are review signals, not diagnoses.

## 17. Explicit Optimization Exclusions

NOT implemented: safety-stock optimization, service-level optimization, EOQ, order quantities, supplier allocation, purchase mix, constrained replenishment, cost optima, supplier ranking/scoring, disruption simulation, Decision Replay, AI Copilot.

## 18. Phase 6 Handoff

Phase 6 (Supplier/Procurement Intelligence) can consume per series: health, projected stockout date, coverage/DOS, reorder urgency, service warnings, forecast uncertainty (point/lower/upper, width), exposure, plus PO/shipment history and supplier-product links. Suggested: join `inventory-intelligence` JSON output to supplier tables by product for exposure-weighted supplier views; no schema change needed.
