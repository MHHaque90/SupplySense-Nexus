# Phase 12A Final Implementation Report — Backend API Foundation

**Project:** SupplySense Nexus
**Phase:** Phase 12A — Backend API Foundation (analytics exposure layer)
**Status:** COMPLETE — all endpoints implemented, tested, documented, and verified live.
**Branch:** `main` working tree (no commits made; user did not request one)
**Verification:** `pytest backend/app/tests/` → **838 passed, 0 failed** (768 baseline + 70 new)
`python -m ruff check backend/app scripts backend/app/tests/api_support.py` → clean
`python -m ruff format --check` → clean
OpenAPI: **24 paths**, all 18 new endpoints present
Live smoke on `http://localhost:8010` → 401 uniform envelope + CORS preflight echoing `http://localhost:5173` with credentials (no wildcard)

---

## 1. Summary

Phase 12A exposes Phases 3–10 analytics through authenticated, org-scoped FastAPI
endpoints under `/api/v1`. Ten routers are registered in `backend/app/main.py`
with domain tags (`auth`, `dashboard`, `forecast`, `inventory`, `suppliers`,
`procurement`, `risk`, `simulation`, `replay`, `optimization`). Compute bodies use
strict Pydantic schemas (`extra="forbid"`); all responses carry the standard
`{success, data, error, meta}` envelope with `data_source_label`.

Per Phase 12A stop conditions: **no new business logic**, **no ranking or
recommendation** (Phase 11 C2 discipline), **no JWT/OAuth**, **no new
dependencies**, **no database schema changes**; org isolation is enforced through
the existing Phase 11 context loaders (`backend/app/ai/tools/_context.py`),
which load and post-filter every frame by `organization_id`.

---

## 2. Implemented endpoints (18)

| Method | Path | Role tier | `data_source_label` | Purpose |
|--------|------|-----------|---------------------|---------|
| GET | /api/v1/auth/me | any active key | derived | Caller identity metadata |
| GET | /api/v1/dashboard/overview | analyst+ | derived | KPI families (demand/inventory/service/procurement) + Phase 7 risk overview |
| GET | /api/v1/forecast | analyst+ | forecast | Paginated forecast series with point/lower/upper intervals |
| GET | /api/v1/inventory/overview | analyst+ | synthetic | Inventory + service KPI families |
| GET | /api/v1/inventory/positions | analyst+ | synthetic | Point-in-time positions per series |
| GET | /api/v1/inventory/health | analyst+ | synthetic | Rule-based health classifications (never predictions) |
| GET | /api/v1/suppliers | analyst+ | synthetic | Deduplicated supplier directory |
| GET | /api/v1/suppliers/performance | analyst+ | synthetic | Descriptive performance facts per supplier (never ranked) |
| GET | /api/v1/procurement/overview | analyst+ | synthetic | Procurement KPI families |
| GET | /api/v1/procurement/open-orders | analyst+ | synthetic | Open PO lines at the analysis date |
| GET | /api/v1/procurement/inbound | analyst+ | synthetic | Inbound coverage states per series (unknowns explicit) |
| GET | /api/v1/procurement/risk | analyst+ | synthetic | Supplier risk-signal rows (never ranked) |
| GET | /api/v1/risk | analyst+ | synthetic | Filterable risk register + full-register overview |
| GET | /api/v1/simulation/events | analyst+ | derived | Phase 8 event vocabulary, templates, probability modes, bounds |
| POST | /api/v1/simulation/run | planner+ | simulated | Monte Carlo disruption simulation over one frozen scenario |
| GET | /api/v1/replay/decisions | analyst+ | derived | Phase 9 decision vocabulary + replay bounds |
| POST | /api/v1/replay/run | planner+ | simulated | Declared arms vs NO_ACTION baseline (factual deltas, no ranking) |
| POST | /api/v1/optimization/run | planner+ | simulated | Phase 10 MILP under one declared objective (solver status only) |

Pagination contract where applicable: `{items, total, page, page_size, has_next}`.

---

## 3. Composition architecture

Read routers compose analytics engines directly (never through the AI tool
handlers, whose truncation bounds would break honest totals):

- KPI / risk / positions / health / inbound / suppliers / procurement →
  `backend/app/api/analytics_support.py` (`load_request_context` → `ctx.load_frames`
  → KPI builders / `describe_open_orders` / `describe_inbound_coverage` /
  `build_supplier_result` / `procurement_risk_signals`), CPU work in
  `starlette.concurrency.run_in_threadpool`, errors mapped via `map_value_errors()`
  (analytics `ValueError` → 422 `VALIDATION_ERROR` with `details.reason`).
- Compute POSTs (`simulation`, `replay`, `optimization`) → shared
  `prepare_api_scenario(...)` (load org-scoped context → exactly one of
  `event_template`/`event_type`; default `SUPPLIER_OUTAGE` template →
  `validate_event` → `validate_scenario_numbers` → `resolve_entities` →
  `build_scenario(scenario_id=f"{run_label}-{uuid4.hex[:10]}")` →
  `resolve_replay_id` → persisted-first `ctx.build_forecasts`; empty forecasts
  → 422 closed) → single adapter copy per package (no private `_xxx` helpers
  across packages):
  - simulation: `runner.run_scenario(...)` + `sim_reports.build_report(...)`
    (mirrors `scripts/analyze_supply_chain.py` CLI path)
  - replay: `decision_from_dict(...)` × declared arms + auto `build_no_action`
    control arm → `run_replay(...)` → `replay_reports.build_report(...)`
    (21 sections, `data_source_label: "simulated"`, no ranking/recommendation)
  - optimization: NO_ACTION replay → `build_shared_baseline(...)` →
    `run_optimization(..., config=OptimizationConfig(...))` → `build_report(...)`
    (`cost_shortage_tradeoff` requires `shortage_penalty > 0`; `time_limit_seconds`
    1–120)
- CPU-bound compute off the event loop via `run_in_threadpool`; async DB/session
  handling throughout.

---

## 4. Security: auth, roles, rate limiting, labels

- **Authentication**: opaque Bearer API keys (`ssk_`), SHA-256 hash stored,
  `hmac.compare_digest`; uniform 401 `UNAUTHORIZED` ("Authentication failed.")
  for missing/malformed/unknown/deactivated keys; identity never from the body.
- **Roles**: GETs = `require_roles(*ANALYST_PLUS)` (analyst/planner/manager/
  executive); POSTs = `require_roles(*PLANNER_PLUS)` (planner/manager/
  executive → analyst receives 403 `FORBIDDEN`); `GET /auth/me` = `get_auth_context`
  only; admin bypasses via `Role.is_admin`; fail closed.
- **Rate limiting**: only the 3 compute POSTs use `enforce_rate_limit` (fail-open
  `InMemoryRateLimiter`, in-memory, per role+user); GETs unlimited (dashboard
  polling can't exhaust the shared budget). Tiers: analyst 100/1000,
  planner 200/2000, manager/executive 500/5000 per hour/day, admin unlimited.
  Denials → 429 `RATE_LIMIT_EXCEEDED` + `Retry-After` + audit row
  `ai.ratelimit.exceeded`. `get_rate_limiter` dependency overridable in tests.
- **Audit**: `simulation.run`, `replay.run`, `optimization.run` audited via
  `support.audit_run(...)` (explicit commit); parameters include scenario_id,
  objective/status, horizon, seed, etc.
- **Data labeling** (never simulated-as-real): `derived` (auth/me, dashboard,
  event/decision contract metadata), `forecast` (forecasts — estimates, not
  actuals), `synthetic` (descriptive reads), `simulated` (compute outputs).
  Every report repeats `data_source_label` at top level plus `meta`.
- **CORS**: origins `http://localhost:3000`, `http://localhost:8080`,
  `http://localhost:5173`; credentials allowed; no wildcard; preflight echoes
  the allowed origin; unknown origins get no `Access-Control-Allow-Origin`.
- **Strict bodies**: Pydantic `extra="forbid"` on all request models → 422 on
  unknown fields (verified by OpenAPI schema `additionalProperties: false`).

---

## 5. Test results

70 new tests across 12 files:

- `backend/app/tests/api_support.py` — shared helper (role-key seeding, two-org
  seeding via `GenerationConfig(organization_count=2)`, org-scoped id sampling,
  envelope/page/error assertions, error-reason flattening)
- `test_auth_api.py` (5): identity shape, no secret leakage, 401 for missing/
  malformed/unknown/inactive keys
- `test_cors.py` (3): no wildcard origin, preflight allows localhost:5173 with
  credentials, unknown origin gets no ACAO header
- `test_openapi_contract.py` (3): all 18 paths + methods registered; compute
  schemas forbid unknown fields; pre-existing `/ai/*` and `/health` routes kept
- `test_dashboard_api.py` (4): envelope/label, KPI family structure, bad date
  422, horizon bounds 422
- `test_forecast_api.py` (5): `forecast` label, row arrays aligned,
  horizon/pagination, reversed window 422, foreign series 422
- `test_inventory_api.py` (6): overview families, positions pagination + product
  filter, health states (STOCKOUT|CRITICAL|AT_RISK|HEALTHY|EXCESS|UNKNOWN),
  foreign product 422
- `test_supplier_api.py` (5): sorted directory, performance window + single
  supplier, no-ranking disclaimer phrases
- `test_procurement_api.py` (7): overview KPIs, open orders pagination + supplier
  filter, inbound coverage states, risk signals, foreign supplier 422
- `test_risk_api.py` (5): register shape (total == overview.records unfiltered),
  severity filter narrows items only, horizon bounds 422, foreign supplier 422
- `test_simulation_api.py` (12): event vocabulary + drift guard
  (`get_args(EventType) == EVENT_TYPES`), happy path, default template, direct
  event type, planner 403, unknown field 422, template+event_type 422,
  explicit probability requires value, deterministic same-seed outcome equality,
  rate-limit 429 envelope + audit row, 401
- `test_replay_api.py` (8): decisions vocabulary + drift guard, declared arm
  report stays unranked (banned-key walk + banned JSON phrases), control-only
  run, unknown decision type 422, unknown field 422, planner 403, audit row
- `test_optimization_api.py` (7): schema literals match `OBJECTIVES`/`STATUSES`,
  solver status reported verbatim (never advice), non-advice limitation phrases,
  banned-key walk on report, tradeoff-without-penalty 422, unknown objective 422,
  unknown field 422, planner 403, audit row

Full regression: **838 passed, 0 failed** (768 baseline + 70 new) in ~16 min.
Per-test isolated `supplysense_test` database with create/drop cleanup; all test
data synthetic.

---

## 6. Verification performed

1. `pytest backend/app/tests/` → 838 passed, 0 failed (coverage maintained;
   no baseline test touched).
2. `python -m ruff check backend/app scripts backend/app/tests/api_support.py` →
   clean (tests dir excluded by project ruff config).
3. `python -m ruff format --check` → clean on API layer, schemas, main.py,
   `api_support.py` (one formatting pass applied).
4. `python -c "import backend.app.main"` OK; `app.openapi()` → 24 paths, all
   18 new endpoints with correct methods.
5. Live smoke on port 8010: 401 envelope, CORS preflight echoing
   `http://localhost:5173` + credentials, no wildcard. Server stopped after
   smoke; no process left running.
6. Git state: 17 modified files (16 baseline + `.env.example` CSV→JSON array
   fix — the CSV form was a genuine app-crash defect on settings load); 13 new
   untracked files; no commits made (not requested).

---

## 7. Docs updated

- `docs/api-contract.md` — rewritten as the honest Phase 12A contract (envelopes,
  labels, roles/rate limits, CORS, error codes, 18-endpoint table, "not yet
  implemented" list, example curl call); earlier draft's 44-endpoint aspirational
  surface removed.
- `docs/roadmap.md` — Phase 12A implementation notes appended (endpoints, auth,
  rate limits, labels, no-C2 deviations, test count, frontend out of phase).
- `docs/development-guide.md` — Phase 12A section added: uvicorn smoke command
  (`--loop none --port 8010`), manual API-key provisioning procedure, example
  calls, CORS origins, label rules; test-count line updated to 838.

Frontend deliverables of Phase 12 proper (Chart.js dashboards, AI copilot UI,
Decision Replay Lab UI) remain out of phase for 12A.

---

## 8. Decisions / deviations recorded

- Routers consume engines directly, not via `ai/tools/_context.py` wrappers — the
  tool adapters' output truncation bounds would produce dishonest totals for
  dashboard reads; loaders remain the single org-scoping boundary.
- GET metadata endpoints (`/simulation/events`, `/replay/decisions`) use
  `ANALYST_PLUS` so analysts can discover contracts; compute POSTs stay
  `PLANNER_PLUS`.
- `ScenarioRequest`: neither `event_template` nor `event_type` defaults to the
  locked `SUPPLIER_OUTAGE` template (docstring corrected accordingly); both →
  422.
- Replay never ranks/recommends/score (Phase 11 C2); `NO_ACTION` control arm
  auto-inserted; empty decisions = baseline outcome only.
- Optimization: four scalar objectives only, no Pareto front, solver status is
  solver vocabulary only, never translated into advice; `ScipyHiGHSSolver`
  (HiGHS via `scipy.optimize.milp`) used since OR-Tools isn't installed here.
- `.env.example` `CORS_ORIGINS` corrected from CSV to JSON array
  (`["http://localhost:3000","http://localhost:8080","http://localhost:5173"]`);
  pydantic-settings would fail to parse CSV at settings load.

---

## 9. Known scope boundaries (not implemented in 12A)

No frontend, no new ingestion/quality/product/governance endpoints, no scenario
CRUD, no decision-option generation endpoint, no `/optimization/{run_id}` GET,
no model registry UI. See `docs/api-contract.md` §"Not yet implemented" and
`docs/roadmap.md` Phase 13 targets.
