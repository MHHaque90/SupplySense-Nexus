# Roadmap: SupplySense Nexus

## Phase 0: Repository Audit and Architecture

### Objectives
- Inspect repository and establish foundation.
- Define product requirements and system architecture.
- Design database schema, API contracts, and analytics architecture.
- Create project documentation and development guidelines.

### Deliverables
- [x] Product requirements document
- [x] System architecture document
- [x] Database design document
- [x] API contract document
- [x] ML architecture document
- [x] Decision engine design document
- [x] AI assistant design document
- [x] Data strategy document
- [x] Testing strategy document
- [x] Roadmap document
- [x] AGENTS.md project instructions
- [x] README.md
- [x] .gitignore, .env.example, pyproject.toml, docker-compose.yml
- [x] Backend scaffold (FastAPI app with health endpoint)
- [x] Frontend scaffold (HTML landing page)
- [x] Initial project configuration files

### Dependencies
- None (all design work is independent).

### Risks
- Documentation may need updates as implementation reveals new requirements.
- Technology choices may need adjustment based on available libraries.

### Verification Checklist
- All 10 documentation files exist and are complete.
- AGENTS.md contains all required sections.
- Project structure follows conventions.
- Health endpoint passes tests.
- FastAPI application imports without errors.

### Definition of Done
- All deliverables are reviewed and validated.
- Health tests pass.
- Documentation is comprehensive and internally consistent.

---

## Phase 1: Data Foundation and PostgreSQL Schema

### Objectives
- Implement PostgreSQL schema with all tables from database design.
- Create SQLAlchemy models and Alembic migrations.
- Set up database connection and session management.
- Implement basic CRUD operations for core entities.

### Deliverables
- SQLAlchemy models for all tables (users, organizations, products, suppliers, etc.)
- Alembic migration scripts
- Database connection pool configuration
- CRUD repository layer
- Unit tests for database operations

### Dependencies
- Phase 0 complete.
- PostgreSQL server running.

### Risks
- Schema complexity may require iterative refinement.
- Migration scripts may need adjustment during development.

### Verification Checklist
- All tables created successfully.
- Migrations run cleanly from scratch.
- CRUD operations work for all core entities.
- Foreign key relationships are enforced.
- All database tests pass.

### Definition of Done
- Database schema is fully implemented.
- All CRUD operations are functional.
- Migration scripts are tested and working.

---

## Phase 2: Data Ingestion and Quality Validation

### Objectives
- Build data ingestion pipeline.
- Implement configurable data-quality validation rules.
- Create data-quality reporting interface.
- Support synthetic data generation for testing.

### Deliverables
- Data ingestion API endpoints
- Data-quality validation engine
- Data-quality report generation
- Synthetic data generator module
- Data lineage tracking

### Phase 2 Implementation Notes (completed)
- Deterministic synthetic ERP generator in `backend/app/data/` (seed 42 default; pure generator functions plus batched async ingestion pipeline).
- Default dataset: 1 organization, 5 users, 24 products, 8 suppliers, 3 warehouses, 365 days (2025-07-01–2026-06-30); ~26k demand observations; POs/shipments/inventory/disruptions generated coherently.
- Data-quality framework (`backend/app/data/quality/`): 63 checks persisted to `data_quality_checks`; inventory and procurement reconciliation included.
- CLI: `scripts/generate_synthetic_data.py` with `generate`, `validate`, `report`, `reset`, `sample` subcommands.
- Sample CSVs in `data/sample/`; dictionary in `data/dictionaries/`.
- All data labeled synthetic (operations) or simulated (disruptions); no forecasts or scenarios generated (later phases).

### Dependencies
- Phase 1 complete.
- Database schema available.

### Risks
- Data validation rules may need refinement based on real-world data patterns.
- Ingestion performance may need optimization for large datasets.

### Verification Checklist
- Data ingestion accepts various file formats.
- Data-quality checks identify known issues.
- Reports are generated correctly.
- Synthetic data generator produces valid datasets.
- Data lineage is tracked for all ingested records.

### Definition of Done
- Data ingestion pipeline is functional.
- Data-quality checks run automatically.
- Reports are generated and accessible.

---

## Phase 3: Demand Forecasting and Inventory Intelligence

### Objectives
- Implement baseline forecasting models (naive, seasonal naive, moving average, exponential smoothing).
- Build feature engineering pipeline.
- Implement time-based walk-forward validation.
- Create inventory intelligence features (position, safety stock, stockout risk).
- Generate forecasts with prediction intervals.

### Deliverables
- Baseline forecasting models
- Time-based validation framework
- Forecast evaluation metrics (MAE, RMSE, MAPE, WMAPE)
- Prediction interval generation
- Inventory position reporting
- Safety stock and reorder point calculations
- Stockout risk estimation

### Dependencies
- Phase 2 complete.
- Clean data available in database.

### Risks
- Baseline model performance may be inadequate for complex demand patterns.
- Feature engineering may need iteration to capture seasonality effectively.

### Verification Checklist
- All baseline models train and predict.
- Time-based validation produces consistent results.
- Evaluation metrics are computed correctly.
- Prediction intervals are calibrated (coverage checks pass).
- Inventory metrics are calculated accurately.
- Forecast results are labeled as simulated/estimated.

### Definition of Done
- Baseline forecasting pipeline is functional.
- Inventory intelligence features are available.
- All models are evaluated and metrics documented.

### Phase 3 Implementation Notes (analytics foundation delivered)
- Delivered as the analytics foundation in `backend/app/analytics/` plus `scripts/analyze_supply_chain.py` (see `docs/analytics-foundation.md`): canonical dataset loaders, leakage-safe features, analytical demand profiling, five baselines (naive, seasonal naive, moving average, drift, SES), six metrics, walk-forward validation, inventory/service/procurement KPIs, JSON+Markdown reporting, 67 tests.
- Prediction intervals, safety-stock/reorder-point optimization, and stockout-risk modeling deferred.

## Phase 4: Demand Forecasting

### Objectives
- Upgrade the baseline foundation with statistical, intermittent-demand, and restrained ML models.
- Add demand-profile-aware routing, seasonality/trend detection, model selection, ensembles, prediction intervals, explainability, confidence, and persistence to the existing schema.
- Provide reproducible, explainable forecasts with structured output for Phase 5.

### Deliverables (implemented, no new tables)
- Holt, Holt-Winters, autoregression, Croston-style intermittent, HistGradientBoosting, zero fallback; routing by observed profile; WAPE-based confidence.
- Intervals from empirical residual quantiles (80/95, floored at zero); interval score.
- Selection with fallback, explainability, and `SelectionResult`/`ForecastOutput` contracts; persistence to `model_versions`/`forecast_runs`/`forecasts` (duplicate-safe, no migration).
- Multi-series evaluation report and CLI `forecast` + `forecast-report` with `--persist`/`--output`.

### Phase 4 Implementation Notes
- Statistical smoothers use fixed documented parameters (deterministic, no optimizer) and demand is floored only at output so backtest metrics stay honest.
- All models share Phase 3 `fit`/`predict` and walk-forward validation.
- No deep learning, no new heavy dependencies; sklearn HGB only where justified.

---

## Phase 5: Inventory Intelligence

### Objectives
- Transform demand forecasts, uncertainty, inventory observations, and service signals into transparent inventory intelligence.
- Provide position, coverage, days of supply, projected trajectories, stockout exposure, health classification, reorder SIGNALS, turnover, aging, anomalies, and concentration analytics.
- Remain descriptive: signals answer "does this position require attention", never optimized decisions.

### Deliverables (implemented, no new tables, no migration)
- `backend/app/analytics/inventory/` (types, position, forecast_inputs, coverage, projection, stockout, health, reorder_signals, uncertainty, service, turnover, aging, anomalies, concentration, reports).
- Persisted-first forecast consumption with public-interface fallback and explicit MISSING_FORECAST states.
- CLI `inventory-intelligence` with health filtering and JSON/Markdown reports.
- 63 tests covering positions, integration, coverage, projection, exposure, all six health states, urgency boundaries, uncertainty, service, turnover, aging, anomalies, reports, and leakage.

### Definition of Done
- Inventory intelligence signals are generated per product/warehouse with forecast provenance.
- Reorder outputs are threshold signals with reasons, never order quantities.
- Safety-stock optimization, inventory optimization, and supplier intelligence explicitly excluded.

### Phase 5 Implementation Notes
- Phase 4 forecasting files untouched; only public selection/reporting/persistence interfaces consumed.
- Known inbound uses undelivered shipments expected inside the horizon only; otherwise demand-only projection (documented assumption).
- Historical backtesting not implemented; persisted forecast history is insufficient.

---

## Phase 6: Supplier and Procurement Intelligence

### Objectives
- Connect Phase 5 inventory exposure with suppliers, relationships, POs, shipments, and delivery history.
- Describe supplier performance, reliability, lead times, open procurement, concentration, and supplier-linked exposure.
- Remain descriptive: no ranking, no recommendations, no optimization.

### Deliverables (implemented, no new tables, no migration)
- `backend/app/analytics/procurement/` (types, supplier_performance, lead_times, delivery, supplier_product, open_orders, inbound, moq, concentration, exposure, service_impact, risk_signals, reports).
- Reliability classes (UNKNOWN/STABLE/VARIABLE/DELAYED/HIGH_DELAY), dependency classes, inbound coverage states, rule-based risk signals.
- CLI `procurement-intelligence` with JSON/Markdown reports.
- Phase 6 tests covering performance, lead times, delivery, relationships, open orders, inbound, MOQ, concentration, exposure, risk, reports, leakage, and integration.

### Definition of Done
- Supplier intelligence describes historical performance with evidence and missing-evidence reporting.
- Risk signals carry reasons, metrics, and severity without scores or rankings.
- Supplier ranking, recommendations, optimization, simulation, and AI Copilot explicitly excluded.

### Phase 6 Implementation Notes
- Phase 4 forecasting and Phase 5 inventory files untouched; only public interfaces consumed.
- Received quantities inferred from delivered shipments linked to POs (documented assumption).
- See `docs/supplier-procurement-intelligence.md` for methodology and the Phase 7 handoff.

---

## Phase 7: Supply-Chain Risk Intelligence

### Objectives
- Transform inventory and procurement intelligence into transparent, explainable supply-chain risk.
- Identify and explain risk across ten domains with evidence, severity, traceability, and monitoring signals.
- Build a filterable risk register and JSON/Markdown reporting without prescribing decisions.

### Deliverables (implemented, no new tables, no migration)
- `backend/app/analytics/risk/` (types, ten domain modules, aggregation, explanations, register, reports).
- Rule-based severity with documented ordering; UNKNOWN preserved for missing evidence, never converted to LOW.
- Hierarchical aggregation with two documented combination boosts; templated explanations.
- CLI `risk-intelligence` with severity/domain/entity filters and JSON/Markdown reports.
- Phase 7 tests covering all domains, aggregation, dependency, leakage, traceability, and language safety.

### Dependencies
- Phase 5 and Phase 6 complete.
- Product, supplier, BOM, inventory, forecast, and procurement data available.

### Risks
- Thin per-relationship histories keep many lead-time records UNKNOWN by design.
- Current synthetic data has no live STOCKOUT series; those paths are unit-tested.

### Verification Checklist
- Risk records carry evidence, metrics, provenance, and explanations.
- Component risks aggregate transparently into overall exposure.
- Missing evidence stays UNKNOWN and never implies low risk.
- Reports label synthetic data and contain no prescriptive language.
- Single-supplier dependencies are identified without sourcing recommendations.

### Definition of Done
- Risk register is fully populated, filterable, and traceable.
- Aggregation is rule-based and explainable.
- All risk analysis features are available via CLI and reports.
- Phase 4 forecasting, Phase 5 inventory, and Phase 6 procurement implementations unchanged.

### Phase 7 Implementation Notes
- See `docs/supply-chain-risk-intelligence.md` for methodology and the Phase 8 handoff.
- No optimization, disruption simulation, Decision Replay, or AI Copilot implemented.

---

## Phase 8: Disruption Simulation

### Objectives
- Implement controlled disruption scenarios with explicit assumptions.
- Build a deterministic daily inventory engine plus Monte Carlo simulation.
- Support combined disruptions with per-component provenance.
- Compare baseline vs disrupted scenario without prescribing decisions.

### Deliverables (implemented, no new tables, no migration)
- `backend/app/analytics/simulation/` (types, events, probability, scenarios, targets, baseline, demand/supply effects, engine, Monte Carlo, runner, outcomes, comparison, traceability, reports).
- Seven event types, four probability modes (empirical contract present but unavailable), deterministic IDs, seeded reproducibility.
- CLI `disruption-simulation` with templates, explicit parameters, distributions, and JSON/Markdown reports.
- Phase 8 tests covering events, probability, scenarios, baseline, engine, Monte Carlo, comparison, traceability, uncertainty, leakage, reports, language, and integration.

### Dependencies
- Phase 7 complete.
- Risk register and dependency exposure available.

### Risks
- No future inbound exists beyond dataset end for some suppliers (zero-effect scenarios are honest mechanics).
- Deep synthetic inventory means many scenarios show no stockouts; deltas still quantify depletion.
- Received quantities inherit Phase 6 inference limits.

### Verification Checklist
- Scenarios validate parameters and target entities explicitly.
- Monte Carlo results reproduce with fixed seeds.
- Combined disruptions apply components with individual provenance.
- Results separate historical observation, scenario assumption, and simulated outcome.
- All simulation outputs are labeled as simulated.

### Definition of Done
- Simulation engine is functional.
- All scenario types are supported.
- Results are reproducible and properly labeled.
- Phase 4 forecasting, Phase 5 inventory, Phase 6 procurement, and Phase 7 risk implementations unchanged.

### Phase 8 Implementation Notes
- See `docs/disruption-simulation.md` for methodology and the Phase 9 handoff.
- No optimization, Decision Replay, AI Copilot, or automated decisions implemented.

---

## Phase 9: Decision Replay Lab

### Objectives
- Implement decision option generation.
- Build Decision Replay Lab comparison engine.
- Create recommendation ranking with confidence scoring.
- Implement assumption tracking and reproducibility.

### Deliverables
- Decision option generation engine
- Scenario comparison framework
- Cost, service, risk, and inventory impact analysis
- Recommendation ranking with confidence scores
- Assumption tracking and documentation
- Reproducibility framework for decisions
- Decision history management

### Dependencies
- Phase 7 complete.
- Simulation engine and scenario infrastructure available.

### Risks
- Recommendation ranking may need business validation.
- Confidence scoring methodology may need refinement.

### Verification Checklist
- Decision options are generated for each scenario.
- Comparisons across options produce meaningful results.
- Recommendations are ranked with confidence scores.
- Assumptions are tracked and documented.
- Results are reproducible with stored parameters.
- Decision history is maintained.

### Definition of Done
- Decision Replay Lab is fully functional.
- All comparison and ranking features work correctly.
- Reproducibility is verified.

### Phase 9 Implementation Notes (completed)
- See `docs/decision-replay-lab.md` for methodology and the Phase 10 handoff.
- Implemented as factual decision comparison: eight decision types, one frozen scenario, one shared baseline, common random numbers, copy-on-write effects, descriptive PASS/UNCHECKED constraint checks, four separated uncertainty categories, and an exactly 21-section report.
- Phase 9 never ranks, never recommends, never scores, and never optimizes; the original ranking/confidence-scoring objectives above are explicitly deferred to Phase 10 optimization scope.
- CLI `decision-replay` is the only Phase 9 user surface: no Phase 9 HTTP endpoints, no database writes, no new tables, no new dependencies.
- Phase 9 tests cover baseline sharing, comparison, constraints, costs, decisions, effects, reproducibility, seeds, targeting, traceability, validation, reports, uncertainty, no-ranking language, no-database access, future-data leakage, and end-to-end integration.

---

## Phase 10: Optimization Engine

### Objectives
- Implement constraint-based optimization using OR-Tools.
- Build multi-objective optimization with Pareto front generation.
- Implement supplier selection and procurement quantity optimization.
- Add budget, capacity, MOQ, lead-time, and service-level constraints.

### Deliverables
- OR-Tools optimization models
- Multi-objective optimization solver
- Constraint validation and violation reporting
- Pareto front generation
- Supplier selection optimizer
- Procurement quantity optimizer
- Replenishment policy optimizer

### Dependencies
- Phase 8 complete.
- Decision engine and scenario infrastructure available.

### Risks
- OR-Tools may have performance issues for large-scale problems.
- Multi-objective optimization may require parameter tuning.

### Verification Checklist
- Optimization models solve feasible problems correctly.
- Infeasible problems are detected and reported.
- Pareto front is generated correctly.
- All constraint types are enforced.
- Optimization results are reproducible.
- Results are labeled as simulated/estimated.

### Definition of Done
- Optimization engine is fully functional.
- All constraint types are implemented.
- Multi-objective optimization produces valid Pareto fronts.

### Phase 10 Implementation Notes (completed)
- Implemented as a deterministic, auditable MILP layer in `backend/app/analytics/optimization/` consuming Phase 9 public outputs only; Phases 4–9 logic and contracts unchanged, no database schema changes, no new dependencies.
- **Documented deviation — solver**: OR-Tools is not installed on this system (Docker unavailable; no package installs allowed in this phase). The solver is `ScipyHiGHSSolver` built on `scipy.optimize.milp` (HiGHS, already a project dependency via scikit-learn's stack). OR-Tools remains the roadmap's future replacement; the solver boundary is isolated in `solver.py`.
- **Documented deviation — multi-objectivity**: instead of Pareto-front generation, the engine exposes exactly four explicit scalar objectives (`minimize_total_cost`, `minimize_shortage`, `cost_shortage_tradeoff`, `maximize_service_fulfillment`); no silent weights, one objective per run, no ranking of alternatives.
- Delivered: typed input extraction from Phase 9/8 datasets, scenario-aware MILP formulation (orders by supplier-product-day, inventory balance, hard/soft demand rows, MOQ binaries, budget/capacity/service constraints), six solver statuses with structural INFEASIBLE diagnostics, 7-check result validation, factual baseline comparison (`optimization_not_resimulated`), exactly 21-section report, CLI `optimization` command (exit codes 0/1/2).
- Constraint set: budget, warehouse capacity (nullable → UNCHECKED), MOQ, supplier-product lead-time horizon, minimum service fulfillment, procurement-quantity bounds, purchase-mode integrality.
- Reporting language: never `best`/`should`/`recommend`/`ideal`/`perfect`; `optimal` is used only as the solver status word. All outputs labeled `synthetic: true`, `data_source_label: "simulated"`.
- Tests: 130 new tests across 11 files (inputs, problem, solve, scenarios, comparison, determinism, leakage, provenance, no-DB, reports, CLI); full regression 665 passed (535 baseline unchanged).
- No HTTP endpoints, no database writes, no audit-trail entries (CLI-only surface, consistent with Phases 8–9).

---

## Phase 11: AI Decision Copilot

**Status: COMPLETE** (implemented, tested, documented; full regression 768 passed, zero failures).

### Objectives
- Implement LLM integration with controlled tool calling.
- Build intent classification and tool routing.
- Implement guardrails and audit logging.
- Add human approval workflow for consequential actions.

### Deliverables
- LLM provider abstraction layer — `backend/app/integration/llm_provider.py` (MockProvider default; `ENABLE_AI_ASSISTANT=true` + `AI_PROVIDER=openai` selects the OpenAI-compatible httpx provider)
- Intent classification system — `backend/app/ai/intents.py` (fixed 8-intent taxonomy, score-based keyword classifier with declaration-order tie-break)
- Tool registry and execution engine — `backend/app/ai/registry.py` + `backend/app/ai/tools/` (13 tools: 7 read-only, 3 compute, 3 executable=false declarations; mutation category empty)
- Guardrail enforcement — `backend/app/ai/guardrails.py` (input injection blocking, output banned-word scrub, secret redaction, bounded text)
- Audit logging for all AI interactions — `backend/app/ai/audit.py` (`ai.chat`, `ai.tool.call`, `ai.approval.decision`, `ai.ratelimit.exceeded`)
- Human approval workflow — `backend/app/ai/approvals.py` + `POST /ai/approval` (decisions recorded; execution never occurs)
- Rate limiting — `backend/app/ai/ratelimit.py` (per-role tiers, in-memory, fail-open limiter / fail-closed auth, 429 + `Retry-After`)
- Evidence-backed response generation — `backend/app/ai/service.py` (two-round plan + synthesis, five-field `AIChatResponse`)
- Opaque Bearer API-key auth (decision C1) — `users.api_key_hash`, `core/security.py`
- PostgreSQL conversation history (decision C4) — `ai_conversations`, `ai_messages`, `ai_approvals` (migration `phase11_ai_copilot`)

### Dependencies
- Phase 9 complete. (Phase 10 also completed; the optimization adapter is available to the copilot.)
- All analytical modules are functional.
- LLM API key configured — **not required**: MockProvider is the default (`ENABLE_AI_ASSISTANT=false`); a cloud key is optional with `ENABLE_AI_ASSISTANT=true` + `AI_PROVIDER=openai` + `OPENAI_API_KEY`.

### Risks
- LLM may hallucinate; guardrails must be robust. — Mitigated: prompts are a second layer; registry/executor/guardrails/approvals enforce rules in code; no-ranking and labeling rules are asserted by tests.
- Tool execution errors must be handled gracefully. — Tool failures surface as reply limitations; crashes masked as internal errors; unknown tools fail closed.
- Rate limiting may affect usability. — Tiered per-role limits with `Retry-After`; limiter fails open on internal fault.

### Verification Checklist
- LLM integration works with replaceable provider. — `get_llm_provider` switches mock/http via settings; both tested.
- Intent classification correctly routes to tools. — Taxonomy + tool-mapping tests.
- Guardrails prevent unauthorized actions. — Injection blocks, banned-word scrub, role gates, empty mutation category, approval-never-executes tests.
- All AI responses include evidence and confidence. — Five-field response contract tests.
- Audit logs capture all interactions. — Audit rows asserted for chat, tool calls, approvals, rate-limit denials.
- Human approval workflow is functional. — End-to-end declare → decide flow; `executed` always false.
- Simulated data is labeled correctly. — `DataSourceLabel` enum validation on evidence; compute tools label `simulated`.

### Definition of Done
- AI Decision Copilot is fully functional. — 3 endpoints live under `/api/v1/ai/*`.
- All guardrails are enforced. — In code, not prompts only.
- Audit and approval workflows are working. — Tested end-to-end.

### Implementation Summary (Phase 11)
- 103 new tests across 7 files (`test_ai_{api,guardrails,ratelimit,provider,registry,tools,service}.py`); full regression 768 passed (665 baseline unchanged).
- Database: migration `phase11_ai_copilot` adds `users.api_key_hash` + 3 AI tables (34 application tables + `alembic_version` = 35 relations in `public`).
- Documentation: `docs/ai-decision-copilot.md`, reconciled `docs/ai-assistant-design.md`, `docs/api-contract.md`, `docs/database-design.md`, `docs/testing-strategy.md`, `docs/system-architecture.md`, `docs/optimization-engine.md` (§17 handoff).
- No new runtime dependencies (httpx already present); ruff clean; `python -c "import backend.app.main"` OK.

---

## Phase 12: Frontend Dashboard

### Objectives
- Build interactive dashboard for all modules.
- Implement Chart.js visualizations.
- Create AI copilot interface.
- Build Decision Replay Lab interface.
- Implement responsive design and accessibility.

### Deliverables
- Interactive dashboard with all module views
- Chart.js visualizations for forecasts, inventory, suppliers, scenarios
- AI copilot chat interface
- Decision Replay Lab comparison interface
- Responsive design for all screen sizes
- Accessible UI with keyboard navigation
- Data labeling (actual, forecast, simulated) in visualizations

### Dependencies
- Phase 10 complete.
- All backend APIs are functional.

### Risks
- Visualization complexity may require performance optimization.
- Responsive design may need iterative refinement.

### Verification Checklist
- Dashboard loads and displays all module data.
- Charts correctly distinguish actual, forecast, and simulated data.
- AI copilot interface works correctly.
- Decision Replay Lab interface is interactive.
- Responsive design works on mobile and desktop.
- Accessibility standards are met.

### Definition of Done
- Frontend dashboard is complete and functional.
- All visualizations are accurate and well-labeled.
- UI is responsive and accessible.

### Phase 12A Implementation Notes (completed - backend API foundation)

- 18 new endpoints under `/api/v1` across 10 routers (auth, dashboard,
  forecast, inventory, suppliers, procurement, risk, simulation,
  replay, optimization); `main.py` registers all 12 routers with domain
  tags; OpenAPI exposes 24 paths including the pre-existing
  `/api/v1/ai/*` and `/health` routes.
- Auth: opaque Bearer API keys (`ssk_`), SHA-256 stored, uniform 401;
  reads gated to analyst+, compute POSTs to planner+; admin bypass;
  compute POSTs rate limited per role (analyst 100/1000, planner
  200/2000, manager/executive 500/5000 per hour/day, admin unlimited),
  fail-open limiter with `Retry-After` and audit rows.
- CORS allows `http://localhost:3000`, `http://localhost:8080`, and
  `http://localhost:5173` with credentials and no wildcard.
- Labels: `derived` for identity/metadata/dashboard, `forecast` for
  forecasts, `synthetic` for descriptive reads, `simulated` for
  simulation/replay/optimization compute — never presented as real data
  (`docs/api-contract.md`).
- No new business logic, no ranking or recommendation (Phase 11 C2),
  no JWT/OAuth, no new dependencies or schema changes; org isolation
  enforced through the existing Phase 11 context loaders.
- Tests: 70 new tests across 12 files (`tests/api_support.py` helper
  plus `test_{auth,cors,openapi_contract,dashboard,forecast,inventory,supplier,procurement,risk,simulation,replay,optimization}_api.py`);
  all new tests pass; ruff clean; live smoke on `:8010` green.
- Frontend deliverables of Phase 12 (Chart.js dashboards, AI copilot
  UI, Decision Replay Lab UI) remain out of phase for 12A.

### Phase 12B Implementation Notes (completed - frontend dashboard)

- React 19.2 + Vite 7.3 + TypeScript 5.9 SPA in `frontend/`, replacing
  the Phase 0 static stub (archived under `frontend/legacy/` with a
  README, not deleted). Runtime dependencies: `react` and `react-dom`
  only — no router/state/chart libraries; routing via a history-API
  hook (`src/router.ts`), charts hand-drawn SVG (`src/components/Charts.tsx`).
- 11 pages (Overview, Forecasts, Inventory, Suppliers, Procurement,
  Risk, Simulation, Decision Replay, Optimization, AI Copilot,
  Settings) consuming only Phase 12A endpoints; compute pages share one
  scenario-composition form mirroring the shared request contract.
- Auth is the Phase 12A opaque Bearer key only: key in per-tab
  sessionStorage (`ssn.api_key`), base URL override `ssn.base_url`
  (default `http://localhost:8010`); never localStorage/cookies/
  logging; identity and role from `GET /auth/me` only; 401 marks the
  key rejected, analysts are honestly blocked from compute POSTs by a
  planner gate mirroring the API's 403.
- Data-labeling discipline: every response's `meta.data_source_label`
  rendered as a chip + persistent footer legend; compute pages banner
  "simulated/illustrative"; empty/error states are honest, the UI never
  invents values; AI Copilot runs against `/ai/chat` (works with the
  offline mock provider) and records approvals without executing them.
- Validation: `tsc --noEmit` clean; 35 vitest + Testing Library tests
  green (client envelope/error families incl. Retry-After, auth storage
  discipline, honest state views, scenario-body contract); production
  build ~94 KB gzip; backend regression 838 tests pass, ruff clean.
- Playwright browser validation against the live API: all 11 pages
  rendered with real data at 1440×900 / 2048×1320 / 390×844; live UI
  runs of simulation (~4 s), replay (~2 s), optimization (~4 s) and one
  copilot chat; invalid-key 401 path verified end-to-end. Two render
  bugs found live were fixed (missing plan blocks in optimization
  reports; duplicate React keys in assumption lists); a route-level
  error boundary was added so render defects cannot white-screen the
  app. Screenshots in `.playwright-mcp/shots/` (scratch, gitignored).

---

## Phase 13: Governance, Testing, Deployment, and Portfolio Packaging

### Objectives
- Implement comprehensive governance features.
- Complete all testing and achieve coverage targets.
- Set up CI/CD pipeline.
- Package the project for portfolio demonstration.
- Final documentation and presentation materials.

### Deliverables
- Model registry with versioning
- Backtesting framework
- Drift monitoring system
- Complete audit logging
- User permissions system
- CI/CD pipeline (GitHub Actions)
- Docker deployment configuration
- Comprehensive test suite with 80%+ coverage
- Performance benchmarks
- Final documentation and presentation
- Portfolio README with demo guide

### Dependencies
- Phase 11 complete.
- All modules are functional.

### Risks
- CI/CD setup may encounter environment-specific issues.
- Final testing may reveal integration issues.

### Verification Checklist
- All governance features are implemented.
- All tests pass with target coverage.
- CI/CD pipeline runs successfully.
- Docker deployment works correctly.
- Performance benchmarks are met.
- Documentation is complete and accurate.
- Portfolio presentation materials are ready.

### Definition of Done
- Project is production-quality and portfolio-ready.
- All modules are implemented and tested.
- Deployment infrastructure is operational.
- Documentation and presentation materials are complete.

---

## Summary Timeline

| Phase | Focus | Duration Estimate |
|-------|-------|-------------------|
| 0 | Audit & Architecture | Complete |
| 1 | Data Foundation | 2-3 weeks |
| 2 | Ingestion & Quality | 2-3 weeks |
| 3 | Forecasting & Inventory | 3-4 weeks |
| 4 | Supplier & Procurement | 2-3 weeks |
| 5 | Risk Mapping | 2 weeks |
| 6 | Disruption Simulation | 2-3 weeks |
| 7 | Decision Replay Lab | 3-4 weeks |
| 8 | Optimization Engine | 2-3 weeks |
| 9 | AI Decision Copilot | 3-4 weeks |
| 10 | Frontend Dashboard | 3-4 weeks |
| 11 | Governance & Deployment | 2-3 weeks |

**Total estimated duration**: 7-9 months (part-time)