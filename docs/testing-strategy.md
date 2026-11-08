# Testing Strategy: SupplySense Nexus

## Overview

The testing strategy ensures reliability, correctness, and reproducibility across all modules. Testing covers unit, integration, API, database, data-quality, forecasting, optimization, simulation, AI, security, regression, and performance domains.

## Unit Testing

### Scope
- Individual functions and methods in isolation.
- Pydantic schema validation.
- Data validation logic.
- Helper utilities.

### Framework
- **pytest** with **pytest-cov** for coverage reporting.
- **mypy** for static type checking.

### Coverage Target
- Minimum 80% line coverage for core modules.
- 100% coverage for critical paths (data validation, security).

### Example Tests
- Product schema validation: Valid and invalid product data.
- Data validation rules: Range checks, format checks, referential checks.
- Configuration loading: Environment variable parsing and defaults.
- Utility functions: Date formatting, string manipulation, etc.

## Integration Testing

### Scope
- Database CRUD operations.
- API endpoint integration.
- Module-to-module communication.
- External service integration (LLM, data sources).

### Framework
- **pytest** with **httpx** for API testing.
- **TestClient** from FastAPI for endpoint testing.
- **SQLAlchemy async session** for database testing.

### Test Data
- Use isolated test databases.
- Each test creates its own data and cleans up afterward.
- Synthetic test data only.

## API Testing

### Scope
- All API endpoints (health, data, forecast, supplier, scenario, decision, optimization, AI, governance).
- Request validation, response shape, error handling.
- Authentication and authorization.

### Tests Per Endpoint
1. **Success case**: Valid request returns 200 with correct response shape.
2. **Validation error**: Invalid request returns 422 with error details.
3. **Authentication**: Missing/invalid credentials return 401.
4. **Authorization**: Insufficient permissions return 403.
5. **Not found**: Non-existent resource returns 404.
6. **Rate limiting**: Excessive requests return 429 with `Retry-After` (implemented for AI endpoints; other endpoints have no rate limiting yet).

### Response Shape Validation
- All responses match Pydantic schemas.
- `data_source_label` is present in all responses.
- Error responses have consistent structure.

## Database Testing

### Scope
- Schema integrity (tables, columns, constraints, indexes).
- Foreign key relationships.
- Data insertion, retrieval, update, deletion.
- Transaction handling and rollback.

### Tests
- Table creation and schema validation.
- Referential integrity enforcement.
- Constraint violations are properly rejected.
- Query performance within acceptable thresholds.
- Migration scripts (Alembic) execute correctly.

## Data-Quality Testing

### Scope
- Completeness checks (null values, missing fields).
- Range checks (valid values, boundaries).
- Uniqueness checks (duplicate detection).
- Referential integrity checks (orphaned foreign keys).
- Temporal consistency checks (ordering, overlaps).

### Tests
- Run data-quality checks on synthetic datasets with known issues.
- Verify that checks correctly identify and report problems.
- Validate that imputation logic works correctly.
- Confirm that data-quality reports are generated accurately.

## Forecast Backtesting

### Scope
- Walk-forward validation of forecasting models.
- Evaluation metric computation (MAE, RMSE, MAPE, WMAPE).
- Prediction interval calibration.
- Model selection logic.

### Tests
- Verify that walk-forward validation produces consistent results.
- Check that forecast intervals have target coverage (e.g., 95% intervals cover 95% of actuals).
- Validate that model selection picks the best performer on validation data.
- Confirm that backtesting results are reproducible with fixed seeds.

**Note**: Metrics are computed during testing but are not pre-claimed or fabricated.

## Optimization Feasibility Testing

### Scope
- Constraint satisfaction verification.
- Solution feasibility checks.
- Infeasible problem detection.
- Performance of solver under various constraints.

### Tests
- Verify that feasible problems return feasible solutions.
- Verify that infeasible problems are correctly identified.
- Check that constraint violations are reported.
- Validate that optimization results match manual calculations for simple cases.
- Confirm that multi-objective optimization produces Pareto-optimal solutions.

## Simulation Reproducibility Testing

### Scope
- Monte Carlo simulation reproducibility.
- Random seed consistency.
- Statistical properties of simulation outputs.

### Tests
- Run the same simulation twice with the same seed; verify identical results.
- Run the same simulation with different seeds; verify different results.
- Verify that sample statistics converge to expected values with sufficient iterations.
- Confirm that scenario parameters are correctly reflected in results.

## AI Tool-Contract Testing

### Scope
- Tool input/output schema validation.
- Tool execution correctness.
- Guardrail compliance.
- Intent classification accuracy.

### Tests
- Verify each tool accepts valid inputs and rejects invalid inputs.
- Verify tool outputs match expected schemas.
- Test guardrail violations: Attempt SQL execution, arbitrary Python execution, procurement modification.
- Verify that AI responses include confidence levels and limitations.
- Test that simulated data is labeled correctly.
- Verify that human approval is required for mutating actions.

## Security Testing

### Scope
- SQL injection prevention.
- Authentication bypass attempts.
- Authorization escalation attempts.
- Input validation and sanitization.
- API key validation.

### Tests
- Attempt SQL injection through all input fields; verify rejection.
- Attempt to access another organization's data; verify rejection.
- Attempt to access protected endpoints without authentication; verify 401.
- Attempt to access admin endpoints with analyst role; verify 403.
- Verify that all inputs are properly sanitized.
- Check for exposed secrets in code and configuration.

## Regression Testing

### Scope
- Ensure new changes don't break existing functionality.
- Run full test suite on every code change.
- Track test coverage over time.

### Strategy
- Automated test suite runs on every pull request.
- Critical path tests run on every commit.
- Full suite runs nightly or on release candidates.
- Any failing test blocks merging.

## Frontend Testing

### Scope
- HTML structure and rendering.
- CSS responsive behavior.
- JavaScript interaction logic.
- Chart.js visualizations.

### Tests
- Page loads correctly and displays all sections.
- Responsive layout works on different screen sizes.
- JavaScript functions execute without errors.
- Data labels are displayed correctly on charts.
- Accessibility: All interactive elements are keyboard-navigable.

### Framework
- Playwright for end-to-end browser testing.
- Manual visual inspection for responsive design.

## Performance Testing

### Scope
- API response times.
- Database query performance.
- Forecast generation time.
- Simulation execution time.
- Concurrency handling.

### Tests
- API endpoints respond within 500ms (95th percentile) for standard queries.
- Database queries complete within acceptable time for dataset sizes.
- Forecast generation completes within 60 seconds for 10K demand observations.
- Monte Carlo simulation with 10K iterations completes within 120 seconds.
- System handles concurrent users without degradation.

### Tools
- **pytest-benchmark** for benchmarking critical functions.
- **Locust** or **k6** for load testing (when implemented).

## Acceptance Criteria

### Phase 0 Acceptance
1. All 10 documentation files are created and complete.
2. AGENTS.md is created with all required sections.
3. Project structure is correct.
4. Health endpoint passes tests.
5. FastAPI application imports without errors.
6. Configuration files are valid.
7. README is complete and accurate.

### Phase 1 Acceptance
1. PostgreSQL schema is implemented and migrations run.
2. Data ingestion endpoints work correctly.
3. Data-quality checks pass for synthetic data.
4. All database tests pass.

### Phase 2 Acceptance
1. Baseline forecasting models are implemented and tested.
2. Forecast backtesting produces valid results.
3. Data-quality reports are generated.

### Phase 3 Acceptance
1. Forecasting models are trained and evaluated.
2. Prediction intervals are computed.
3. Inventory intelligence features work correctly.

### Phase 4+ Acceptance
- Each phase has its own acceptance criteria defined in the roadmap.

## Test Data Policy

- All test data is synthetic or generated.
- No real company data is used in testing.
- Test databases are isolated from production databases.
- Test data is cleaned up after each test run.

## Phase 2 Test Coverage (implemented)

- `test_synthetic_generators.py` (14 tests): config defaults, synthetic naming, safe domains and test-only passwords, catalog profiles/tiers, supplier profile variety, single-source first component, shared components, BOM cycle rejection, demand continuity and non-negativity, intermittent zero days, zero-demand edge case, disruption labeling, opening-balance policy, dataset consistency.
- `test_synthetic_ingestion.py` (8 tests): successful ingestion with real counts, transaction rollback on bad records, batch insertion, duplicate-generation guard, safe reset and regeneration, quality suite on generated data, same-seed reproducibility, different-seed divergence.
- `test_data_quality.py` (9 tests): foreign-key validation, uniqueness and provenance, temporal consistency, BOM cycle detection, inventory reconciliation, procurement reconciliation, expected ranges, full suite with zero failures, sample export plus dictionary generation.
- Reproducibility compares deterministic business fields (UUIDs and timestamps are ingestion-assigned and excluded).

## Phase 3 Test Coverage (implemented, 67 tests)

- `test_analytics_datasets.py` (6 tests): demand/inventory/procurement/sales/supplier extraction, column contracts and dtypes, date and dimension filters, day/week/month aggregation, empty-dataset frames.
- `test_analytics_features.py` (9 tests): lags, rolling windows excluding the current day, future-perturbation leakage check, calendar attributes, intermittent gaps, documented zero-fill, constant/zero series, short history, movement signs.
- `test_demand_profiling.py` (9 tests): stable, trending, volatile, intermittent, constant, zero, empty series, seasonality data sufficiency, dataset grouping.
- `test_forecast_baselines.py` (9 tests): all five baselines, history validation, horizon validation, registry.
- `test_forecast_metrics.py` (9 tests): normal/perfect/constant data, MAPE zero masking and all-zero NaN, sMAPE bounds, length mismatch, empty/non-finite rejection.
- `test_walk_forward.py` (8 tests): fold ordering, leakage exclusion, multi-model/multi-metric, insufficient history, model skips, determinism, per-series comparison wording.
- `test_inventory_kpis.py` (8 tests): latest on-hand, levels, stockouts, turnover proxy, days of supply, movement, reconciliation pass/fail, KPI metadata contract, empty frames.
- `test_service_procurement_kpis.py` (6 tests): fulfillment denominators, demand fulfillment, PO/lead-time totals, delivered-only shipment rates, MOQ compliance, descriptive concentration.
- `test_analytics_reports.py` (3 tests): JSON structure and disclaimer, forecast section, analytical Markdown wording.

## Phase 5 Test Coverage (implemented, 63 tests)

- `test_inventory_position.py` (6 tests): latest snapshot, recent statistics and movement, warehouse separation, unknown state, point-in-time discipline, future-perturbation stability.
- `test_forecast_integration.py` (5 tests): persisted grouping with latest-origin-wins, empty frame, explicit missing state, generated fallback provenance, contract serialization.
- `test_coverage_dos.py` (7 tests): normal/high/low/zero demand, unbounded vs unknown states, labeled historical DOS, negative-value visibility.
- `test_projection.py` (5 tests): depletion, known receipts, full coverage, pending-shipment inbound mapping, demand-only fallback.
- `test_stockout.py` (5 tests): immediate, projected within horizon, watch, no exposure, unknown states.
- `test_inventory_health.py` (9 tests): all six states (STOCKOUT/CRITICAL/AT_RISK/HEALTHY/EXCESS/UNKNOWN), threshold boundaries, service-warning path.
- `test_reorder_signals.py` (7 tests): no_signal/monitor/plan/urgent/unknown, documented buffer, missing inputs.
- `test_uncertainty.py` (3 tests): three-case terminology, missing forecast, bound ordering.
- `test_service_turnover_aging.py` (8 tests): repeated-stockout warnings, turnover proxy/trend, movement-age wording, drop/negative/adjustment/stagnant anomalies, concentration shares.
- `test_inventory_reports.py` (3 tests): summary counts, JSON structure and labeling, Markdown sections and wording.
- `test_inventory_leakage.py` (2 tests): position and full-result stability under future perturbation.
- `test_inventory_intelligence.py` (3 tests): persisted-first then generated fallback, full tiny-dataset intelligence, missing-forecast unknown states.
- Leakage coverage: point-in-time discipline asserted at position and result level, mirroring Phase 3/4 perturbation tests.

## Phase 4 Test Coverage (implemented, 60 tests)

- `test_statistical_models.py` (8 tests): Holt, Holt-Winters, AR, Croston (including all-zero and sparse), Zero, registry, determinism.
- `test_routing.py` (10 tests): zero, constant, trending, intermittent, stable, short-history gating, ML opt-in, generator-profile isolation, trend and seasonality detection.
- `test_ml_forecasting.py` (6 tests): HGB determinism, short-history rejection, leakage-safe feature set, future-perturbation, finite predictions, temporal order.
- `test_ensemble.py` (4 tests): weight normalization, average and weighted predictions, walk-forward validation, empty-history rejection.
- `test_selection.py` (8 tests): seasonal selection, zero without fallback, short fallback, forced model, failed forced-model fallback, audit metadata, family mapping, model building.
- `test_intervals.py` (7 tests): ordering, narrower levels, zero floor, all-zero, unsupported levels, interval score, filtered residuals.
- `test_forecast_contracts.py` (3 tests): field defaults, selection contract, point-forecast flooring at assembly.
- `test_persistence.py` (4 tests): version creation and reuse, forecast persistence with duplicate-skip, missing-user error, helper signature.
- `test_explainability.py` (4 tests): model-specific, seasonal, fallback, confidence categories.
- `test_forecast_reporting.py` (4 tests): multi-series structure, zero series, max-series limit, Markdown wording.
- Plus 2 carryover fixes verified in earlier Phase 4 runs (bias arithmetic and volatile profile).

## Phase 6 Test Coverage (implemented)

- `test_supplier_performance.py` (6 tests): PO/shipment aggregation, on-time and delay calculation, lead-time calculation, missing evidence, future-record exclusion.
- `test_leadtime_delivery.py` (8 tests): lead-time statistics, percentile gating, empty observations, UNKNOWN/STABLE/HIGH_DELAY/DELAYED/VARIABLE boundaries.
- `test_supplier_product.py` (4 tests): relationship aggregation, warehouse-level exposure preservation, stockout tracking, missing history.
- `test_open_orders.py` (4 tests): remaining quantities, overdue detection, expected arrivals, empty states.
- `test_inbound_moq.py` (6 tests): supported/partial/insufficient/no-known/unknown inbound, MOQ compliance and ratios, missing terms.
- `test_concentration.py` (5 tests): spend/quantity/PO shares, dependency classes, category and exposure concentration.
- `test_exposure.py` (3 tests): exposure counts with traceability, empty intelligence, contract serialization.
- `test_risk_signals.py` (7 tests): all five signal states, overdue elevation, uncertainty/concentration evidence, no-ranking wording.
- `test_procurement_reports.py` (3 tests): JSON structure and labeling, all 22 Markdown sections, prescriptive-language ban.
- `test_service_impact.py` (3 tests): co-occurrence wording without causality, no-delay and healthy exclusions.
- `test_procurement_leakage.py` (4 tests): future PO/shipment/shipment-event and open-order exclusion.
- `test_procurement_intelligence.py` (2 tests): full tiny-dataset supplier build with traceability, inbound states and dependency classes.

## Phase 7 Test Coverage (implemented)

- `test_risk_inventory.py` (5 tests): stockout-to-critical mapping, DOS bands, healthy LOW, unknown position, traceability fields.
- `test_risk_supplier.py` (5 tests): high delay, variable lead time, insufficient observations, unknown history, linked stockout exposure.
- `test_risk_procurement.py` (4 tests): overdue elevation, clean open orders, empty open evidence.
- `test_risk_dependency.py` (6 tests): single/multi supplier, fanout shares, warehouse breadth, unknown history, no-diversification wording.
- `test_risk_service.py` (5 tests): repeated stockouts, affirmed warnings, delay association without causality, healthy LOW, unknown history.
- `test_risk_concentration_leadtime.py` (6 tests): share bands, unknown shares, empty rows, highest state, lead-time bands, sample gating.
- `test_risk_uncertainty_inbound.py` (8 tests): wide spread, limited confidence, low uncertainty, missing forecast, inbound supported/insufficient/partial/unknown.
- `test_risk_evidence.py` (5 tests): UNKNOWN gap records, empty gaps, deterministic IDs, severity ordering, serialization.
- `test_risk_aggregation.py` (6 tests): max-severity combination, documented boosts, empty aggregation, supplier aggregation, explanation wording, register filters.
- `test_risk_reports.py` (4 tests): JSON structure and labeling, all 25 Markdown sections, prescriptive-language ban, empty report and exposure ordering.
- `test_risk_leakage.py` (4 tests): future inventory/PO/shipment exclusion, service window exclusion, shipment-event independence.
- `test_risk_integration.py` (2 tests): end-to-end register with all domains and traceability, filter behavior with component citations.

## Phase 8 Test Coverage (implemented)

- `test_simulation_events.py` (9 tests): all seven event types, parameter validation, combined components, templates, scenario language.
- `test_simulation_probability.py` (7 tests): deterministic/explicit modes, bounds, provenance values, empirical unavailability, triangular/uniform distributions.
- `test_simulation_scenarios.py` (7 tests): contract validation, horizon/count bounds, invalid events, explicit/supplier/risk-record targeting, template coverage.
- `test_simulation_baseline.py` (4 tests): generation, reproducibility, disruption-free state, transparent short-forecast extension.
- `test_simulation_engine.py` (8 tests): depletion/unmet mechanics, inbound arrival, delay shifting, stockout semantics, demand shock, supply reduction, warehouse unavailability.
- `test_simulation_monte_carlo.py` (7 tests): seed reproducibility/variation, count-gated percentiles, bounded distributions, empty inputs.
- `test_simulation_comparison.py` (3 tests): delta calculations, None handling, zero deltas.
- `test_simulation_traceability.py` (2 tests): full provenance chain, event-less trace.
- `test_simulation_uncertainty.py` (4 tests): four-concept separation, severity/probability distinction, horizon gating, affected counts.
- `test_simulation_leakage.py` (5 tests): future inventory/demand/PO/shipment/supplier exclusion, horizon-bounded windows.
- `test_simulation_reports.py` (3 tests): JSON structure and labeling, all 21 Markdown sections, prescriptive-language ban.
- `test_simulation_language.py` (3 tests): event/probability/report wording without predictions or prescriptions.
- `test_simulation_integration.py` (2 tests): end-to-end outage and Monte Carlo demand spike with reproducibility.

## Phase 9 Test Coverage (implemented)

- `test_replay_baseline.py` (7 tests): baseline built once and shared, every arm references it, baseline labeled not an arm, Phase 8 baseline/delta parity, arms never modify it, scenario never mutated.
- `test_replay_comparison.py` (8 tests): every baseline delta key, pairwise coverage in declared order, right-minus-left semantics, order-swap sign flip, identical-arm zeros, None propagation, no ranking fields, recorded-delta helper.
- `test_replay_constraints.py` (7 tests): MOQ pass/fail, nullable capacity as UNCHECKED, warehouse capacity, available inventory, supplier-product links, lead-time evidence, timing window notes.
- `test_replay_costs.py` (6 tests): observed purchase cost, explicit assumed cost, missing cost stays None, disruption rate required, negative cost rejected, no best/optimal cost keys.
- `test_replay_decisions.py` (6 tests): decision contract fields, deterministic ids, all eight decision types, NO_ACTION control, COMBINED_ACTION rules, decision_from_dict parsing.
- `test_replay_effects.py` (9 tests): one group per decision type, copy-on-write inputs untouched, allocation split exactly once, transfer conservation, combined order/nesting.
- `test_replay_reproducibility.py` (6 tests): identical inputs reproduce results, NO_ACTION equals Phase 8 outcome, report reproducibility, seed/count metadata effects, deterministic replay id.
- `test_replay_seed.py` (7 tests): identical samples per seed, variation across seeds, one fingerprint per arm, sampling once per run, deterministic empty sample set, count-driven samples, inputs never consumed.
- `test_replay_targeting.py` (11 tests): supplier/product/warehouse targeting, explicit alternative-supplier selection, link requirements, scenario membership accept/reject, transfer membership, known-allocation suppliers.
- `test_replay_traceability.py` (6 tests): decision fields on every trace, Phase 8 provenance preserved, chain order, decision-assumption text, baseline_ref consistency, effect notes.
- `test_replay_validation.py` (12 tests): valid decision passes, unknown ids/quantities/timing rejected, supplier-product links, insufficient source inventory, transfer rules, membership, component order, unknown type at construction.
- `test_replay_reports.py` (8 tests): exactly 21 sections, no extras, simulated metadata, DECISION_ASSUMPTION labels, cost provenance labels, no-ranking limitations, ordered Markdown headings, JSON serializability.
- `test_replay_uncertainty.py` (7 tests): four separated categories, notes never scores, inherited forecast uncertainty, scenario scope, variability metadata, decision layer contents, report/Markdown rendering.
- `test_replay_noranking.py` (7 tests): no banned keys in run/report/results, no banned heading words, pairwise semantics, required no-ranking statements, no recommended/ranked JSON fields.
- `test_replay_nodb.py` (4 tests): no database imports, no raw SQL, frames-not-sessions signature, no session objects at module level.
- `test_replay_leakage.py` (4 tests): future snapshots/POs/shipments excluded from baseline, arms, and report; analysis date recorded with exclusion limitation.
- `test_replay_integration.py` (5 tests): all eight decision types end-to-end with report pipeline and time budget, one shared fingerprint, validation/constraint/effect notes per arm, complete decision-scoped chains, baseline/delta contract.

## Phase 10 Test Coverage (implemented, 130 tests)

- `test_optimization_inputs.py` (18 tests): typed-contract validation errors, order arrival day = lead − 1, eight exclusion reasons (missing/nonpositive/out-of-horizon lead, scenario-eliminated, scope, unit-cost), scope filters, unconditional warehouse masking mirroring `run_entity_once`, demand-shock window, inbound pass-through, point-parameter assumptions, baseline unmet parity with the inventory engine, provenance and forecast references.
- `test_optimization_problem.py` (21 tests): config validation for all four objectives, objective metadata, problem-id stability and scoping inputs, orders-only decision variables with integrality, hard vs soft demand-satisfaction rows, MOQ/capacity/budget/service rows, unit-cost-missing offer exclusion, zero-column NO_DATA formulation, parameter declarations, matrix shapes.
- `test_optimization_solve.py` (18 tests): six statuses (OPTIMAL/FEASIBLE/INFEASIBLE/UNBOUNDED/ERROR/NO_DATA), structural INFEASIBLE diagnostics, short-outage OPTIMAL breakdown with 7/7 PASS checks and binding rows, shortage/tradeoff/maximize objectives, budget and minimum-fulfillment enforcement, continuous-mode UNCHECKED integrality, solver identity disclosure, timing keys and labels with a 5 s ceiling.
- `test_optimization_scenarios.py` (10 tests): warehouse disruption → INFEASIBLE with availability rows, demand shock raises demand/cost, supply reduction factor, lead-time delay arrival day, delay clipping at horizon − 1, combined-event components, simulation_count/seed excluded from problem id, scenario change included.
- `test_optimization_comparison.py` (7 tests): baseline comparison arithmetic and notes, unavailable-solution note wording, evaluate-plan by entity, Phase 9 deltas with `optimization_not_resimulated`, missing control arm, JSON serializability.
- `test_optimization_determinism.py` (6 tests): identical runs excluding timings, stable problem id and decision ordering, byte-identical report JSON and Markdown after timing normalization, reproducible matrices.
- `test_optimization_leakage.py` (5 tests): future-poisoned snapshots/POs/shipments change nothing downstream, analysis date recorded, forecast origins bounded by the analysis date.
- `test_optimization_provenance.py` (9 tests): Phase 9 lineage fields, forecast references, simulated labeling, report/problem provenance equality, documented OR-Tools deviation, warning dedup, nullable capacity disclosed as UNCHECKED, uncertainty intervals, scenario section.
- `test_optimization_nodb.py` (5 tests): no database imports or raw SQL in the package, payload-only entry signature, clean module namespace, `AsyncSessionLocal` untouched during a run.
- `test_optimization_reports.py` (15 tests): exactly 21 ordered sections, numbered Markdown headings, banned-word scan (`best`/`should`/`recommend`/`ideal`/`perfect`) on feasible and infeasible reports, decision-value shape, binding/slack grouping, assumptions, deterministic Markdown, all four objectives.
- `test_optimization_cli.py` (16 tests): end-to-end run writing JSON + Markdown with exit 0, stdout emission, exit-2 argument paths (scenario/objective/budget/fulfillment/horizon/date validation, malformed scenario JSON, DB offline), exit-1 empty datasets, shortage objective, banned-word Markdown scan, output-path error handling.

Full regression after Phase 10: **665 passed** (535 baseline + 130 new), zero failures.

## Phase 11 Test Coverage (implemented, 103 tests)

- `test_ai_api.py` (10 tests): health endpoints stay public, missing/malformed/unknown/inactive-key 401 (uniform "Authentication failed." envelope), identity-in-body rejection, chat happy path with conversation/message persistence, foreign conversation 404, role separation across endpoints, tools listing with banned tool names absent, generated key format (`ssk_` + token_urlsafe) and SHA-256 hash.
- `test_ai_guardrails.py` (27 tests): parametrized input-injection blocks (instruction override, table dumps, SQL/Python execution, role override) vs allowed normal asks, refusal responses free of banned wording, output scrub for each banned pattern (best/should/recommend/ranked/preferred/top choice), clean text untouched, key-shape redaction, runaway-text truncation, all-removed fallback, exact redaction count.
- `test_ai_ratelimit.py` (8 tests): tier table matches design (analyst 100/1000 … admin unlimited), 101st-request denial, sliding hour window, daily-cap scope, admin unlimited, fail-open on limiter fault, 429 with `Retry-After` + `ai.ratelimit.exceeded` audit row, chat endpoint 429 envelope end-to-end.
- `test_ai_provider.py` (14 tests): MockProvider plan/synthesis validity, provider construction validation (empty/unknown key, disabled flag → mock, unknown name), `get_llm_provider` misconfiguration → 503, httpx OpenAI-compatible success, transient-429 retry then success, bounded retries → 503, non-retryable 400 fast-fail, malformed body → 503, transport failure bounded, `describe()` never exposes the API key.
- `test_ai_registry.py` (15 tests): default-registry invariants (13 tools, empty mutation), duplicate/bad-category rejection, executable-mutation rejection, declaration rules, unknown tool → 404, sorted/category-filtered listing, parameter validation (extra fields, types, bounds), execute audited once (success and validation failure), declarations have no execution path, unknown tool fails closed, role gate + admin bypass, crash masked as internal error, registry cache/reset.
- `test_ai_tools.py` (18 tests): all seven read tools return labeled evidence (parametrized), org isolation with a second generated organization, foreign-product 403-style rejection, planning-role gates, Phase 8 simulation / Phase 9 replay / Phase 10 optimization integration (incl. unknown-objective rejection, offline-demo arm labeling), scenario parameter validation, declarations cannot execute while audit accumulates, module exports.
- `test_ai_service.py` (11 tests): fixed 8-intent taxonomy, tool-selection mapping, tool round cap + evidence, tool errors surfaced as limitations, approval flow never executes, input-refusal persisted + audited, output scrub applied to provider wording, unknown tool skipped with limitation, bounded history with explicit marker (and marker text), message labels + conversation state.

Full regression after Phase 11: **768 passed** (665 baseline + 103 new), zero failures.

## Test Reporting

- Test results are reported in CI/CD pipeline output.
- Coverage reports are generated for each test run.
- Failed tests are categorized and prioritized.
- Test results are archived for trend analysis.