# Analytics Foundation: SupplySense Nexus (Phase 3)

**Phase 3 provides the analytical foundation. Production-grade demand forecasting is Phase 4. Advanced inventory intelligence is Phase 5. Supplier/procurement intelligence is Phase 6.**

All analytics operate on SYNTHETIC data. Analytical wording only: the synthetic dataset shows patterns; nothing here describes real business performance.

## 1. Architecture

```
backend/app/analytics/
    __init__.py        synthetic disclaimer
    config.py          AnalyticsConfig (horizons, windows, metrics)
    types.py           KPIResult, SeriesProfile, ModelComparison, errors
    datasets/          DB access lives here ONLY (column-only SELECTs)
        demand.py      canonical demand frame + day/week/month aggregation
        inventory.py   snapshots (+unit-cost basis) and transactions
        procurement.py PO lines + supplier terms; shipments + delay days
        sales.py       order headers and enriched lines
        suppliers.py   suppliers with product links
    features/
        calendar_features.py  day-of-week, week, month, quarter, year, weekend
        demand_features.py    lags, rolling stats, intermittency, trend
        inventory_features.py signed quantities, daily movement
        supplier_features.py  lead-time and shipment summaries (descriptive)
        profiles.py           analytical demand profiling
    forecasting/
        baselines.py   Naive, SeasonalNaive, MovingAverage, Drift, SES
        metrics.py     MAE, RMSE, MAPE (zero-safe), sMAPE, WAPE, bias
        validation.py  walk-forward evaluator + per-series comparison
        result.py      ForecastResult, ValidationFold
    kpis/
        demand_kpis.py, inventory_kpis.py, procurement_kpis.py, service_kpis.py
    reports/
        analytics_report.py  full JSON + Markdown report
        forecast_report.py   baseline evaluation section
        inventory_report.py  inventory section
```

Separation: extraction → transformation → features → modeling → validation → reporting. Pure functions never write to the database and hold no global state.

## 2. Analytical Datasets

Canonical frames with explicit dtypes (VARCHAR numerics parsed to float, dates normalized). Filters: date range, product/warehouse/supplier ids, organization. Empty filters return typed empty frames. Aggregation preserves totals across grains.

## 3. Feature Engineering

Lags 1/7/14/28, rolling means 7/14/28, rolling std 7/28, coefficient of variation, zero-ratio/nonzero-count/avg/median/min/max over 28 days, trailing OLS trend slope, full calendar attributes, days-since-previous-nonzero. Continuity policy: missing calendar days are zero-filled with a `was_imputed_zero` flag (documented imputation, not observed demand).

## 4. Demand Profiling

Rule-based profiles from observed statistics: zero, constant, intermittent (40%+ zeros), trending (slope × n / mean ≥ 0.3), volatile (CV > 0.8), stable. Weekly seasonality strength needs ≥ 28 observations and is reported separately, never claimed from less.

## 5. Baseline Forecasting

Consistent `fit(history)` / `predict(horizon)` interface. Seasonal naive requires history ≥ season length and raises `InsufficientHistoryError` otherwise; walk-forward records such models as skipped with reasons. No ML, no neural networks, no new dependencies (NumPy only).

## 6. Validation

Rolling-origin evaluation: train `series[:cutoff]`, score `series[cutoff:cutoff+horizon]`, advance by step. Supports training window/minimum history via `min_history`, multiple models and metrics. Deterministic. Model comparison selects the lowest-error model PER SERIES under the configured metric with explicit non-global wording.

## 7. Metrics

MAE, RMSE, bias always defined; MAPE masks zero actuals (NaN if all zero — prefer WAPE/sMAPE for intermittent demand); sMAPE in [0, 2] with 0/0 → 0; WAPE NaN on zero total actual.

## 8. Inventory KPIs

Current on-hand (latest snapshot), average/min/max/volatility, stockout count/rate/zero days, unit-based turnover proxy (documented: no COGS in schema), days of supply (needs positive average demand), signed movement, ledger-vs-closing reconciliation. Quantity-based only; no monetary inventory value is reported.

## 9. Procurement KPIs

PO count, ordered quantity, synthetic spend total, contracted vs realized lead times, on-time/late rates over delivered shipments, average delay, MOQ compliance, top-supplier share and HHI (descriptive only).

## 10. Leakage Prevention

Rolling statistics operate on `shift(1)` series; lags never include the current target; walk-forward never trains on future observations. Tests perturb future values and assert past features are unchanged, and verify a post-spike cutoff cannot see the spike during training.

## 11. Synthetic-Data Limitations

See `reports/analytics_report.py::LIMITATIONS`. Status-based fill rates are proxies; turnover is unit-based; concentration is descriptive; seasonality needs sufficient history; MAPE is unreliable for intermittent demand.

## 12. CLI Usage

```bash
python scripts/analyze_supply_chain.py demand --aggregation week
python scripts/analyze_supply_chain.py inventory --product-id <uuid>
python scripts/analyze_supply_chain.py procurement --supplier-id <uuid>
python scripts/analyze_supply_chain.py forecast --forecast-horizon 28 --metric mae
python scripts/analyze_supply_chain.py report --output-json report.json --output-markdown report.md
```

Fails cleanly (exit 1/2 with messages) on unavailable DB, empty datasets, unknown entities, insufficient history, and invalid dates. No secrets printed.

## 13. Testing Strategy

67 Phase 3 tests: 6 loader tests against a tiny isolated Phase 2 dataset; the rest on deterministic in-memory fixtures (fast, no DB dependence). Leakage tests would fail if future values entered features.

## 14. Phase 4 Handoff

Phase 4 (production forecasting) can reuse: canonical demand frames + aggregation, leakage-safe feature frames, `SeriesProfile` for model routing, the `fit/predict` baseline interface as benchmark competitors, `walk_forward` + metrics for backtesting, and `ModelComparison` output format. Suggested: add candidate models behind the same interface, extend metrics, persist chosen model metadata (new capability, not a schema change to existing tables).
