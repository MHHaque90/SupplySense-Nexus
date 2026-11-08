# Development Guide: SupplySense Nexus

## Prerequisites

- Python 3.12+ (3.14.7 verified)
- PostgreSQL 17 running on port 5432
- Databases `supplysense` and `supplysense_test` created
- Dependencies installed from `pyproject.toml`

## Environment

Copy `.env.example` to `.env`. Never commit `.env` or secrets. The default
`DATABASE_URL` targets the local `supplysense` database with no secrets.

AI provider settings (Phase 11): `ENABLE_AI_ASSISTANT=false` (default) keeps the
deterministic MockProvider — no API key needed. To use a cloud endpoint set
`ENABLE_AI_ASSISTANT=true`, `AI_PROVIDER=openai`, and `OPENAI_API_KEY` (httpx
only; a misconfigured provider returns 503 `AI_UNAVAILABLE`). Optional knobs:
`AI_MODEL` (default `gpt-4o-mini`), `AI_REQUEST_TIMEOUT_SECONDS` (30),
`AI_MAX_HISTORY_MESSAGES` (12), `AI_MAX_TOOL_CALLS_PER_TURN` (8).

## Database Migrations

```bash
python -m alembic upgrade head
```

## Synthetic Data (Phase 2)

**This dataset is synthetic and is generated solely for demonstration, testing, analytics development, and portfolio purposes.**

```bash
# Full default dataset: seed 42, 1 org, 24 products, 8 suppliers,
# 3 warehouses, 365 days (2025-07-01 to 2026-06-30)
python scripts/generate_synthetic_data.py generate --seed 42

# Custom scale
python scripts/generate_synthetic_data.py generate --seed 7 --product-count 40 \
  --supplier-count 12 --warehouse-count 4 --history-days 180

# Quality checks, counts, samples, scoped reset
python scripts/generate_synthetic_data.py validate
python scripts/generate_synthetic_data.py report
python scripts/generate_synthetic_data.py sample
python scripts/generate_synthetic_data.py reset
```

- Without `--reset`, generation refuses to duplicate an existing dataset.
- With `--reset`, only the SupplySense synthetic tables are cleared in FK-safe order.
- Configuration lives in `backend/app/data/config.py` (`GenerationConfig`).
- Generators are pure functions in `backend/app/data/generators/`; persistence lives in `backend/app/data/ingestion/`; checks and reporting in `backend/app/data/quality/`.

## Tests

```bash
pytest backend/app/tests/ -v
python -m ruff check backend/ scripts/
```

Phase 1 tests (16) plus Phase 2 tests (31) plus Phase 3 tests (67) plus Phase 4 tests (60) plus Phase 5 tests (63) plus Phase 6 tests (55) plus Phase 7 tests (59) plus Phase 8 tests plus Phase 9 tests (120) plus Phase 10 tests (130) plus Phase 11 tests (103) must all pass — full regression after Phase 11: **768 passed**. Phase 12A adds **70** new tests (12 files) — full regression after Phase 12A: **838 passed**. Test files use the
isolated `supplysense_test` database with per-test create/drop cleanup. Loader, persistence, and intelligence integration tests build tiny
Phase 2 datasets per test; all other analytics tests run on deterministic in-memory fixtures.

## Analytics (Phase 3)

```bash
python scripts/analyze_supply_chain.py demand --aggregation week
python scripts/analyze_supply_chain.py inventory --product-id <uuid>
python scripts/analyze_supply_chain.py procurement --supplier-id <uuid>
python scripts/analyze_supply_chain.py forecast --forecast-horizon 28 --metric mae
python scripts/analyze_supply_chain.py report --output-json report.json --output-markdown report.md
```

- Analytics code lives in `backend/app/analytics/`; database access only in `datasets/` loaders.
- Pure functions are deterministic and leakage-safe; see [docs/analytics-foundation.md](analytics-foundation.md).
- All reports are labeled SYNTHETIC.

## Forecasting (Phase 4)

```bash
python scripts/analyze_supply_chain.py forecast \
  --product-id <uuid> --warehouse-id <uuid> --forecast-horizon 28 --metric wape --season 7

python scripts/analyze_supply_chain.py forecast-report \
  --forecast-horizon 14 --max-series 20 --output-json report.json

# Persist to model_versions / forecasts (no migration)
python scripts/analyze_supply_chain.py forecast --product-id <uuid> --warehouse-id <uuid> --persist
```

- Forecasting lives in `backend/app/analytics/forecasting/`; see [docs/demand-forecasting.md](demand-forecasting.md).
- Statistical models use fixed smoothing parameters (no optimizer); ML uses random_state=0.
- Intervals are empirical residual quantiles; not guarantees.

## Inventory Intelligence (Phase 5)

```bash
python scripts/analyze_supply_chain.py inventory-intelligence \
  --forecast-horizon 28 --health AT_RISK --output-json inventory.json
```

- Intelligence code lives in `backend/app/analytics/inventory/`; consumes Phase 3 loaders and Phase 4 forecast contracts.
- Reorder outputs are threshold SIGNALS, never order quantities; see [docs/inventory-intelligence.md](inventory-intelligence.md).
- Phase 4 forecasting files are frozen; import and consume their interfaces.

## Supplier & Procurement Intelligence (Phase 6)

```bash
python scripts/analyze_supply_chain.py procurement-intelligence \
  --forecast-horizon 28 --include-exposure --include-concentration \
  --output-json procurement.json --output-markdown procurement.md
```

- Intelligence code lives in `backend/app/analytics/procurement/`; see [docs/supplier-procurement-intelligence.md](supplier-procurement-intelligence.md).
- Descriptive only: no ranking, no recommendations, no optimization, no causal claims.
- Phase 4 forecasting and Phase 5 inventory files are frozen; consume their public interfaces.

## Risk Intelligence (Phase 7)

```bash
python scripts/analyze_supply_chain.py risk-intelligence \
  --forecast-horizon 28 --severity HIGH \
  --output-json risk.json --output-markdown risk.md
```

- Intelligence code lives in `backend/app/analytics/risk/`; see [docs/supply-chain-risk-intelligence.md](supply-chain-risk-intelligence.md).
- Risk identification and explanation only; no optimization, simulation, Replay, or Copilot.
- Phase 4, Phase 5, and Phase 6 files are frozen; consume their public interfaces.

## Disruption Simulation (Phase 8)

```bash
python scripts/analyze_supply_chain.py disruption-simulation \
  --scenario SUPPLIER_OUTAGE --supplier-id <uuid> --horizon-days 28 \
  --output-json sim.json --output-markdown sim.md
```

- Simulation code lives in `backend/app/analytics/simulation/`; see [docs/disruption-simulation.md](disruption-simulation.md).
- Baseline-vs-scenario only; hypothetical outcomes labeled simulated, never predictions.
- Phase 4, 5, 6, and 7 files are frozen; consume their public interfaces.

## Decision Replay (Phase 9)

```bash
python scripts/analyze_supply_chain.py decision-replay \
  --scenario SUPPLIER_OUTAGE --supplier-id <uuid> --horizon-days 28 \
  --output-json replay.json --output-markdown replay.md
```

- Replay code lives in `backend/app/analytics/replay/`; see [docs/decision-replay-lab.md](decision-replay-lab.md).
- Factual comparison only: one frozen scenario, one shared baseline, no ranking or recommendations.

## Optimization Engine (Phase 10)

```bash
python scripts/analyze_supply_chain.py optimization \
  --start-date 2026-06-01 --end-date 2026-06-30 \
  --scenario SUPPLY_REDUCTION --supplier-id <uuid> \
  --objective minimize_total_cost --horizon-days 28 \
  --output-json optimization.json --output-markdown optimization.md
```

- Optimization code lives in `backend/app/analytics/optimization/`; see [docs/optimization-engine.md](optimization-engine.md).
- Runs the Phase 9 replay (NO_ACTION arm) in-process for baseline context, then builds and solves the MILP; exit codes 0 (completed, any solver status), 1 (no data), 2 (invalid arguments / DB offline).
- Four explicit scalar objectives; never `best`/`should`/`recommend` language; all outputs labeled simulated.

## AI Decision Copilot (Phase 11)

```bash
# API key (opaque, shown once): generate + store the SHA-256 hash
python -c "import sys; sys.path.insert(0, '.'); from backend.app.core.security import generate_api_key; raw, h = generate_api_key(); print(raw)"

curl -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Authorization: Bearer ssk_..." -H "Content-Type: application/json" \
  -d '{"message": "Show inventory health for warehouse 3."}'
```

- Copilot code lives in `backend/app/ai/` (service, intents, prompts, guardrails, ratelimit, audit, approvals, memory) plus `backend/app/ai/tools/`; endpoints in `backend/app/api/ai_router.py`; provider abstraction in `backend/app/integration/llm_provider.py`.
- Auth: opaque Bearer keys only — `users.api_key_hash` stores the SHA-256; uniform 401 on any failure; identity never from the request body. Chat/tools need analyst+; approval decisions need manager+.
- Guardrails are enforced in code: injection blocking, output banned-word scrub (no best/should/recommend/rank/preferred/top choice), secret redaction, empty mutation category, approvals never execute.
- Rate limits: analyst 100/1000, planner 200/2000, manager 500/5000, executive 500/5000 per hour/day; admin unlimited; 429 + `Retry-After`.
- History is PostgreSQL-backed (`ai_conversations`, `ai_messages`, `ai_approvals`); see [docs/ai-decision-copilot.md](ai-decision-copilot.md).

## Phase 12A Dashboard API (backend foundation)

```bash
# Local smoke test (port 8010; 8000 may be occupied on this machine)
python -m uvicorn backend.app.main:app --loop none --port 8010
```

Base URL: `http://localhost:8010/api/v1`. Ten routers are registered
with domain tags (`auth`, `dashboard`, `forecast`, `inventory`,
`suppliers`, `procurement`, `risk`, `simulation`, `replay`,
`optimization`) exposing 18 endpoints; OpenAPI lists 24 paths including
the pre-existing `/api/v1/ai/*` and `/health` routes.

**API key provisioning** (no user-management endpoint exists yet —
insert manually or via the synthetic generator):

```bash
python -c "from backend.app.core.security import generate_api_key; raw, h = generate_api_key(); print(raw)"
```

Then insert a `users` row with `api_key_hash = <SHA-256 of the raw key>`,
a role in (`analyst`, `planner`, `manager`, `executive`, `admin`),
`is_active = true`, and an `organization_id`. Every request sends
`Authorization: Bearer ssk_...`; identity never comes from the body.

Example calls:

```bash
curl http://localhost:8010/api/v1/auth/me \
  -H "Authorization: Bearer ssk_..."

curl http://localhost:8010/api/v1/dashboard/overview \
  -H "Authorization: Bearer ssk_..."

curl -X POST http://localhost:8010/api/v1/simulation/run \
  -H "Authorization: Bearer ssk_..." \
  -H "Content-Type: application/json" \
  -d '{"event_template":"SUPPLIER_OUTAGE","horizon_days":14,"simulation_count":5}'
```

- CORS allows `http://localhost:3000`, `http://localhost:8080`, and
  `http://localhost:5173` (dashboard dev server) with credentials and
  no wildcard.
- Role gates: reads need `analyst+`; compute POSTs need `planner+`
  (analyst gets 403); compute POSTs are rate limited per role with
  `Retry-After` and are audited (`simulation.run`, `replay.run`,
  `optimization.run`).
- Labels: `derived` for identity/metadata/dashboard, `forecast` for
  forecasts, `synthetic` for descriptive reads, `simulated` for compute
  outputs — never presented as real data. See `docs/api-contract.md`
  for the full contract.

## Frontend (Phase 12B)

React 19 + Vite 7 + TypeScript SPA in `frontend/`, consuming only the
Phase 12A API contract. No extra runtime dependencies (no router, state,
or chart libraries): routing is a small history-API hook
(`src/router.ts`), charts are hand-drawn SVG (`src/components/Charts.tsx`).

```bash
# Terminal 1 — backend (must use --loop none on this Windows machine)
python -m uvicorn backend.app.main:app --loop none --port 8010

# Terminal 2 — dashboard (strictly on port 5173, a CORS-allowed origin)
cd frontend
npm install
npm run dev
```

- Open `http://localhost:5173`; the app starts locked. Enter an API key
  under **Settings** — it is stored in this tab's sessionStorage only
  (`ssn.api_key`), cleared when the tab closes, never logged or rendered
  outside a password-type input. Identity/role always come from
  `GET /auth/me` — the UI never fabricates them.
- Default backend URL `http://localhost:8010`; overridable per session
  (`ssn.base_url`) from Settings.
- Pages: Overview, Forecasts, Inventory, Suppliers, Procurement, Risk,
  Simulation, Decision Replay, Optimization, AI Copilot (works with the
  offline mock provider), Settings. Analysts are honestly blocked from
  the three compute POSTs (planner+ gate mirrors the API's 403).
- Every response's `meta.data_source_label` is rendered as a chip
  (derived / forecast / synthetic / simulated) plus a legend in the
  footer; compute pages carry an explicit "simulated/illustrative"
  banner. Empty/error states are honest — the UI never invents values.

```bash
# Quality gates (all green after Phase 12B)
cd frontend
npx tsc --noEmit      # type check
npm test              # 35 vitest tests (client, auth, labels, states, scenario contract)
npm run build         # type check + production bundle (~94 KB gzip)
```

## Conventions

- Type hints on all signatures; async/await for I/O; SQLAlchemy ORM only.
- All synthetic records carry `data_source_label = "synthetic"`; disruptions carry `"simulated"`.
- Never present synthetic or simulated data as real data.
