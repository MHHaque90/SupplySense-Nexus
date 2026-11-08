# Demand Forecasting: SupplySense Nexus (Phase 4)

**SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE.** All forecasts describe synthetic generated demand under the current simulation configuration.

Phase 3 provided naive, seasonal naive, moving average, drift, and SES, leakage-safe features, walk-forward validation, and metrics. Phase 4 extends that foundation into a production-oriented forecasting capability without rebuilding it.

## 1. Forecasting Architecture

```
forecasting/
    baselines.py      Phase 3 baselines (reused unchanged)
    models.py         Phase 4 statistical + ML models (Holt, Holt-Winters, AR, Croston, HGB)
    decomposition.py  Trend assessment and seasonality detection
    routing.py        Demand-profile-aware candidate routing
    intervals.py      Empirical residual-quantile prediction intervals
    ensemble.py       Equal-weight and inverse-error ensembles
    selection.py      Per-series model selection with fallback
    explainability.py Evidence-backed reasons and confidence descriptors
    persistence.py    Reuse of model_versions / forecast_runs / forecasts (no migration)
    validation.py     Phase 3 walk-forward (reused)
    metrics.py        Phase 3 metrics (reused)
    result.py         ForecastResult, ValidationFold, SelectionResult, ForecastOutput
reports/
    forecasting_report.py  Multi-series evaluation and Markdown rendering
```

All models share `fit(history)` / `predict(horizon)` and raise `InsufficientHistoryError` instead of producing invalid output. Smoothing parameters are fixed documented defaults (deterministic, no optimizer).

## 2. Model Families

- **Baseline (Phase 3):** zero (deterministic for all-zero series), naive, seasonal naive, moving average, drift, SES.
- **Statistical:** Holt trend, Holt-Winters (additive, 2 full seasons required), autoregression AR(p) via least squares.
- **Intermittent:** Croston-style per-period rate (size/interval smoothing, floored interval, deterministic zero for all-zero history).
- **ML:** HistGradientBoostingRegressor (random_state=0, 90-observation minimum) on leakage-safe lags, rolling, and calendar features with recursive extension.
- **Ensemble:** average and inverse-error-weighted averages, compared like any other model and selected only on validation.

No PyTorch, TensorFlow, Prophet, or GPU dependencies. Existing deps only (numpy, pandas, scikit-learn, statsmodels available but not required for the hand-rolled smoothers).

## 3. Demand-Profile Routing

Observed `SeriesProfile` drives candidates (never the generator's source label):

- zero → zero
- constant → naive, moving_average, ses
- intermittent → croston, moving_average, naive
- stable → naive, moving_average, ses, holt (+ seasonal models if a 7-day cycle is detected)
- trending → drift, holt, autoreg, moving_average
- volatile → moving_average, ses, naive, holt
- seasonal → seasonal_naive, holt_winters, holt, moving_average

History gates remove unsupported models up front (e.g. Holt-Winters needs 2 seasons, AR needs 2p+4, HGB needs 90). ML requires explicit `--include-ml`. Seasonal augmentation uses `detect_seasonality` which needs two full cycles and a 25% weekday/weekend gap.

## 4. Feature Engineering

Phase 3 leakage-safe features reused unchanged. The HGB feature set (`ML_FEATURE_COLUMNS`) uses the same `shift(1)` rolling and lag definitions plus `days_since_nonzero`; recursive prediction appends a zero placeholder at the future date so every future row's features use only prior observations.

## 5. Validation

Phase 3 walk-forward reused: train `series[:cutoff]`, score `series[cutoff:cutoff+horizon]`, step by `validation_step`. Residuals pooled per model for intervals. No random splitting, no shuffling, no future leakage.

## 6. Model Selection

Per series: profile → route → gate → walk-forward each candidate → score by configured metric → lowest-error selected. Wording is narrow: "Selected for this series under this validation configuration." Warnings explain exclusions; if every candidate fails, a structured fallback (naive or zero) is returned. Training window, demand profile, candidates, skipped reasons, explanation, and confidence travel in `SelectionResult`.

## 7. Prediction Intervals

Empirical residual quantiles at 80% and 95% (configurable, validated levels). Methodology, lower/upper, and in-sample coverage travel in `IntervalResult`. Intervals are not guarantees; synthetic empirical coverage does not imply real-world coverage. Demand is non-negative, so point forecasts are floored at zero at output time (raw backtest predictions stay unclamped for honest metrics) and interval lowers are also floored.

## 8. Explainability

Templated, evidence-backed strings per model family (no SHAP, no causal claims). Examples:
- "Seasonal Naive selected because the seasonal cycle produced the lowest validation MAE."
- "Holt selected because the series showed sustained trend and outperformed baseline models."
- "Croston selected because intermittent-demand rate estimation produced the lowest validation error."
Fallback and insufficient-history reasons are equally structured.

Confidence is a descriptor with evidence (`folds`, WAPE-based error, volatility, zero_ratio), not a probability:
- strong ≥5 folds, WAPE <0.2, volatility <0.8, zero_ratio <0.2
- moderate ≥3 folds, WAPE <0.4
- limited otherwise; insufficient if no folds or no error

## 9. Persistence

Existing tables reused, no migration:
- `model_versions` — one row per (model_name, version "4.0.0") with JSON `metrics` (validation, profile, candidates, config) and `model_type` family.
- `forecast_runs` — one row per selection with validation JSON.
- `forecasts` — one row per product/warehouse/date with point/lower/upper, `confidence_level`, `forecast_horizon_days`, `data_source_label="simulated"`, `model_version_id`.

Duplicate-safe: existing versions reused; existing forecast dates skipped (`inserted`/`skipped` counts returned). Requires at least one `users` row for `registered_by`.

## 10. CLI

Forecasting extends the analytics CLI (no second framework):

```bash
python scripts/analyze_supply_chain.py forecast \
  --product-id <uuid> --warehouse-id <uuid> \
  --forecast-horizon 28 --metric wape --season 7 \
  --min-history 90 --validation-windows 10 \
  --model holt_winters --include-ml \
  --output forecast.json --persist

python scripts/analyze_supply_chain.py forecast-report \
  --forecast-horizon 14 --max-series 20 --include-ml \
  --output-json report.json --output-markdown report.md
```

All original `demand`/`inventory`/`procurement`/`report` commands remain. Error handling: unavailable DB, empty data, unknown series, duplicate dates, insufficient history, unsupported model — each fails cleanly with exit 1/2 and no secrets.

## 11. Synthetic-Data Limitations

- All forecasts are of synthetic generated demand.
- Zero-series forecasts are deterministic zeros.
- Constant series avoid complex models by routing.
- Intervals describe in-sample backtest dispersion, not future guarantees.
- Model comparison is descriptive and configuration-specific; no global winner.

## 12. Failure / Fallback Behavior

Insufficient history → `InsufficientHistoryError` surfaced as "Insufficient history: ..." (exit 1). No candidate validates → fallback result with `fallback_used=true` and explanatory warning. Future leakage tests perturb trailing values and assert past features and past folds are unchanged.

## 13. Phase 5 Handoff

Phase 5 (Inventory Intelligence) can consume:
- `ForecastOutput` / `SelectionResult` per product/warehouse (point, lower, upper, horizon, dates, model, profile, validation, confidence, explanation)
- `forecasts` / `model_versions` / `forecast_runs` rows
- `SeriesProfile` and `validation` folds for safety-stock and stockout-risk modeling
- Demand, inventory, and procurement frames as before

Suggested: join forecasts to inventory snapshots by product/warehouse/date for coverage and reorder-point calculations; no schema change needed.
