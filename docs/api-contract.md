# API Contract: SupplySense Nexus (Phase 12A)

Backend foundation exposing Phases 3–10 analytics through authenticated,
org-scoped endpoints under `/api/v1`. Frontend work (Phase 12 proper,
including Chart.js dashboards) is not part of this phase.

## Authentication

Opaque Bearer API keys (`ssk_...` prefix); the server stores only a
SHA-256 hash and compares with `hmac.compare_digest`. There is no JWT,
no login endpoint, and identity is never accepted from the request body.
`GET /api/v1/health` is public; every other endpoint fails closed with a
uniform 401 (`UNAUTHORIZED`) whether the key is missing, malformed,
unknown, or belongs to a deactivated user.

## Envelopes

Every response follows one of two envelopes. `meta` always carries
`timestamp` (ISO 8601) and `data_source_label`.

Success:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "meta": {
    "timestamp": "2026-10-19T12:00:00Z",
    "data_source_label": "synthetic",
    "source": "phase3_kpis"
  }
}
```

Error (no `data` field):

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "...",
    "details": { "reason": "..." }
  },
  "meta": { "timestamp": "...", "data_source_label": "synthetic" }
}
```

## Data labeling

All API responses carry `data_source_label` in `meta`, and every report
payload repeats its label at top level. Labels used by this phase:

| Endpoints | `data_source_label` | Meaning |
|-----------|---------------------|---------|
| `GET /auth/me`, `GET /simulation/events`, `GET /replay/decisions`, `GET /ai/tools` | `derived` | Static identity / contract metadata |
| `GET /dashboard/overview` | `derived` | KPI families + risk overview over synthetic data |
| `POST /ai/chat`, `POST /ai/approval` | `derived` | Assistant answers and approval records over the caller's own organization data |
| `GET /forecast` | `forecast` | Estimates with uncertainty intervals, never actuals |
| `GET /inventory/*`, `GET /suppliers/*`, `GET /procurement/*`, `GET /risk` | `synthetic` | Descriptive rows over the synthetic dataset |
| `POST /simulation/run`, `POST /replay/run`, `POST /optimization/run` | `simulated` | Conditional outcomes, never predictions |

Never present synthetic or simulated data as real data; forecast outputs
are always labeled estimated/simulated.

Health endpoints (`GET /health`, `/health/live`, `/health/ready`) return a
plain status object without the standard envelope and carry no
`data_source_label`.

## Roles and rate limiting

Read endpoints (`GET`) require `analyst` or above (`ANALYST_PLUS`).
Compute endpoints (`POST`) require `planner` or above (`PLANNER_PLUS`);
an analyst receives 403 (`FORBIDDEN`). `GET /auth/me` needs only an
active key. An admin role bypasses role gates.

Compute POSTs (`/simulation/run`, `/replay/run`, `/optimization/run`)
and the three AI endpoints (`/ai/chat`, `/ai/tools`, `/ai/approval`)
are rate limited per role with a shared budget and a fail-open limiter.
Read endpoints are unlimited so dashboard polling cannot exhaust the
shared budget. Rejections return 429 `RATE_LIMIT_EXCEEDED`
with a `Retry-After` header.

Approval decisions move a pending approval to `approved` or `rejected`
(terminal states; a decision on an already-decided approval returns 409
`CONFLICT`). Approvals never execute any action.

| Role | Per-hour tier | Per-day tier |
|------|---------------|--------------|
| analyst | 100 | 1,000 |
| planner | 200 | 2,000 |
| manager / executive | 500 | 5,000 |
| admin | unlimited | unlimited |

Audit rows are written for `simulation.run`, `replay.run`,
`optimization.run`, and rate-limit denials (`ai.ratelimit.exceeded`).

## CORS

Allowed origins: `http://localhost:3000`, `http://localhost:8080`,
`http://localhost:5173`; credentials allowed; no wildcard. Preflight
echoes the allowed origin; unknown origins receive no
`Access-Control-Allow-Origin` header.

## Error codes

| Code | Status | Meaning |
|------|--------|---------|
| UNAUTHORIZED | 401 | Missing, malformed, unknown, or deactivated key |
| FORBIDDEN | 403 | Role lacks permission for the endpoint |
| VALIDATION_ERROR | 422 | Bad request body/query (strict bodies reject unknown fields) |
| RATE_LIMIT_EXCEEDED | 429 | Per-role limit exceeded; `Retry-After` included |
| INTERNAL_ERROR | 500 | Unexpected failure (details never exposed) |
| AI_UNAVAILABLE | 503 | LLM provider failure after bounded retries |
| FEATURE_DISABLED | 403 | Capability disabled by configuration (`ENABLE_SIMULATION` / `ENABLE_OPTIMIZATION` off) |

## Implemented endpoints (Phase 12A)

All paths are under `/api/v1`. Responses paginate as
`{items, total, page, page_size, has_next}` where applicable.

| Method | Path | Role tier | Label | Purpose |
|--------|------|-----------|-------|---------|
| GET | /auth/me | any active key | derived | Caller identity metadata |
| GET | /dashboard/overview | analyst+ | derived | KPI families (demand/inventory/service/procurement) + risk overview |
| GET | /forecast | analyst+ | forecast | Paginated forecast series with point/lower/upper intervals |
| GET | /inventory/overview | analyst+ | synthetic | Inventory + service KPI families |
| GET | /inventory/positions | analyst+ | synthetic | Point-in-time inventory positions per series |
| GET | /inventory/health | analyst+ | synthetic | Rule-based health classifications (never predictions) |
| GET | /suppliers | analyst+ | synthetic | Deduplicated supplier directory |
| GET | /suppliers/performance | analyst+ | synthetic | Descriptive performance facts per supplier (never ranked) |
| GET | /procurement/overview | analyst+ | synthetic | Procurement KPI families |
| GET | /procurement/open-orders | analyst+ | synthetic | Open PO lines at the analysis date |
| GET | /procurement/inbound | analyst+ | synthetic | Inbound coverage states per series (unknowns explicit) |
| GET | /procurement/risk | analyst+ | synthetic | Supplier risk-signal rows (never ranked) |
| GET | /risk | analyst+ | synthetic | Filterable risk register + full-register overview |
| GET | /simulation/events | analyst+ | derived | Phase 8 event vocabulary, templates, probability modes, bounds |
| POST | /simulation/run | planner+ | simulated | Monte Carlo disruption simulation over one frozen scenario |
| GET | /replay/decisions | analyst+ | derived | Phase 9 decision vocabulary + replay bounds |
| POST | /replay/run | planner+ | simulated | Declared decision arms vs NO_ACTION baseline (factual deltas, no ranking) |
| POST | /optimization/run | planner+ | simulated | Phase 10 MILP under one declared objective (solver status only) |
| GET | /health | public | — | Application health check (plain status object; no envelope) |
| GET | /health/live | public | — | Liveness probe |
| GET | /health/ready | public | — | Readiness probe (PostgreSQL connectivity) |
| POST | /ai/chat | analyst+ | derived | One bounded chat turn; MockProvider unless `ENABLE_AI_ASSISTANT=true` |
| GET | /ai/tools | analyst+ | derived | Tool registry listing (executable tools and `requires_approval` flags) |
| POST | /ai/approval | manager+ | derived | Human approve/reject decision on a declared action; 409 if already decided; never executes |

## Feature flags

`ENABLE_SIMULATION` and `ENABLE_OPTIMIZATION` default to `false`. When a
flag is off, the corresponding compute POST returns `403
`FEATURE_DISABLED`` before any computation or rate-limit accounting
occurs; no audit row is written and no solver or simulation computation
runs. Set the flag to `true` (via `.env`/environment) to enable the
capability; the corresponding frontend page renders the returned error
honestly instead of fabricating a report.

All POST bodies use strict schemas (`extra="forbid"`): unknown fields are
rejected with 422. Compute bodies share `ScenarioRequest` — exactly one of
`event_template` (default `SUPPLIER_OUTAGE`) or `event_type` may be
provided (neither defaults to the template). Horizon 1–180 days
(default 28); simulation count 1–500 (default 20).

## Not yet implemented (future phases)

The following endpoints appear in earlier drafts of this document and
remain unimplemented: `POST /api/v1/data/ingest`,
`GET/POST /api/v1/products*`, `GET /api/v1/inventory/safety-stock`,
`GET /api/v1/inventory/stockout-risk`,
`GET /api/v1/inventory/transactions`,
`GET /api/v1/inventory/turnover`,
`GET /api/v1/suppliers/{id}/scorecard`,
`GET /api/v1/suppliers/alternatives/{product_id}`,
`GET /api/v1/suppliers/concentration`,
`GET/GET /api/v1/forecasts/{id}`, `GET /api/v1/forecasts/compare`,
`GET /api/v1/forecasts/drift`,
`GET /api/v1/risk/dependency-map`,
`GET /api/v1/risk/single-point-of-failure`,
`GET /api/v1/risk/propagation/{entity_id}`,
`POST /api/v1/scenarios`, `GET /api/v1/scenarios/{id}`,
`POST /api/v1/scenarios/{id}/simulate`,
`GET /api/v1/scenarios/{id}/sensitivity`,
`POST /api/v1/decision-options`,
`GET /api/v1/decision-comparisons/{scenario_id}`,
`POST /api/v1/decision-comparisons/{scenario_id}/rank`,
`GET /api/v1/decision-history`,
`GET /api/v1/optimization/{run_id}`,
`GET /api/v1/optimization/pareto-front`,
`GET/POST /api/v1/governance/*`. None of these exist in the codebase;
see `docs/roadmap.md` for phase targets. No frontend (Chart.js)
dashboard endpoints exist yet either.

## Example call

```bash
curl -X POST http://localhost:8010/api/v1/simulation/run \
  -H "Authorization: Bearer ssk_..." \
  -H "Content-Type: application/json" \
  -d '{"event_template":"SUPPLIER_OUTAGE","horizon_days":14,"simulation_count":5}'
```
