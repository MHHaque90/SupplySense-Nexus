# AI Decision Copilot: SupplySense Nexus (Phase 11)

**Implementation reference for Phase 11.** Design rationale lives in
[docs/ai-assistant-design.md](ai-assistant-design.md); the HTTP contract lives in
[docs/api-contract.md](api-contract.md). All outputs described here are labeled
(`public`, `synthetic`, `user-provided`, `derived`, `simulated`, `forecast`) and
simulated/estimated values are always identified as such.

## 1. What was built

A natural-language copilot over the platform's evidence:

| Layer | Module | Responsibility |
|---|---|---|
| HTTP | `backend/app/api/ai_router.py` | `POST /ai/chat`, `GET /ai/tools`, `POST /ai/approval` under `/api/v1` |
| Service | `backend/app/ai/service.py` | Two-round pipeline: plan (intent + tool calls) → execute → synthesize; history persistence; audit |
| Intents | `backend/app/ai/intents.py` | Deterministic 8-intent classifier + default tool mapping |
| Prompts | `backend/app/ai/prompts.py` | System prompt + round-2 tool-results message (second layer only) |
| Registry | `backend/app/ai/registry.py` | `ToolSpec` registration, JSON-Schema validation, role gates, audited execution |
| Tools | `backend/app/ai/tools/` | 13 registered tools (7 read-only, 3 compute, 3 declarations) |
| Guardrails | `backend/app/ai/guardrails.py` | Input-injection blocking, output banned-word scrub, secret redaction, text bounds |
| Rate limit | `backend/app/ai/ratelimit.py` | Per-user sliding hour/day windows, tier table, fail-open |
| Approvals | `backend/app/ai/approvals.py` | Declarations → human decision (recorded, never executed) |
| Memory | `backend/app/ai/memory.py` | PostgreSQL conversation history, bounded |
| Audit | `backend/app/ai/audit.py` | Append-only `audit_events` writes |
| Provider | `backend/app/integration/llm_provider.py` | `LLMProvider` protocol, MockProvider (default), HttpOpenAIProvider (httpx) |
| Auth | `backend/app/core/security.py` | Opaque Bearer API keys, `AuthContext`, role checks |
| Schema | `backend/app/models/ai.py` + migration `phase11_ai_copilot` | `ai_conversations`, `ai_messages`, `ai_approvals`, `users.api_key_hash` |

## 2. Request lifecycle (`POST /ai/chat`)

1. **Auth (fail-closed)**: `Authorization: Bearer ssk_...` → SHA-256 hash →
   `hmac.compare_digest` against `users.api_key_hash`; user must be active.
   Any failure → uniform 401 `UNAUTHORIZED` / "Authentication failed."
   Identity comes only from the principal — never the request body.
2. **Rate limit (fail-open)**: sliding hour/day window for the user's role;
   exceeded → 429 `RATE_LIMIT_EXCEEDED` + `Retry-After` + `ai.ratelimit.exceeded`
   audit row (explicitly committed before the raise).
3. **Conversation**: resolve/create the org+user scoped `AiConversation`;
   append the user turn (`data_source_label = "user-provided"`).
4. **Input guardrail**: injection patterns (instruction override, data-dumping,
   SQL/Python execution, role override) → refusal reply, persisted and audited —
   never forwarded to the provider.
5. **Intent + plan**: `classify()` scores keyword groups (highest score wins,
   declaration-order tie-break; 0.75 with tools / 0.60 `general_inquiry`) and
   `select_tools()` maps intent → default tools, adding
   `run_optimization_analysis` on optimization vocabulary. In offline mode the
   plan comes from this classifier; with a provider it comes from round 1.
6. **Tool execution**: each call is registry-validated (schema, roles, category)
   and executed with the org scope; a per-turn tool-call cap
   (`AI_MAX_TOOL_CALLS_PER_TURN`, default 8) bounds work. Failures surface as
   reply `limitations`; unknown tools fail closed; crashes are masked as
   "Tool execution failed." (details never leak).
7. **Synthesis**: round 2 over `TOOL_RESULTS` (echo values only, carry labels).
8. **Output guardrail**: banned-word scrub (best / should / recommend* / ranked /
   preferred / top choice), secret redaction, runaway-text truncation; violations
   are recorded in `limitations`.
9. **Persist + audit**: assistant turn (`derived`), optional `AiApproval`
   declarations, `ai.chat` + `ai.tool.call` audit rows; response envelope meta
   carries `conversation_id`, `session_id`, `intent`, `provider`,
   `approval_ids`, `data_source_label: "derived"`.

## 3. Endpoints

| Endpoint | Roles | Notes |
|---|---|---|
| `POST /api/v1/ai/chat` | analyst, planner, manager, executive, admin | Body: `{message, conversation_id?, session_id?}` (identity never accepted). Response: exactly `{response, confidence, evidence[], limitations[], approved}`. |
| `GET /api/v1/ai/tools` | analyst+ | Optional `?category=`; entries: `{name, description, category, parameters, executable, requires_approval}`. |
| `POST /api/v1/ai/approval` | manager, executive, admin | Body: `{approval_id, decision: approve|reject, comment?}`. Response: `{approval_id, action, status, decided_at, executed}` with `executed` always `false`. 404 unknown, 409 already decided, 403 analyst/planner. |

Evidence items are `{source, label, timestamp, confidence?, limitations[]}` with
`label` validated against the `DataSourceLabel` enum.

## 4. Tool inventory (13 registered, mutation category empty)

**Read-only analytics (7)** — labels: `forecast` for `get_forecast`, otherwise `synthetic`/`derived` per source:
`get_forecast`, `get_inventory_position`, `get_inventory_health`,
`get_supplier_scorecard`, `get_inventory_kpis`, `get_data_quality_report`,
`get_risk_report`.

**Compute (3)** — outputs labeled `simulated` (top-level `data_source_label`
defaulted on every report):
`run_disruption_simulation` (Phase 8), `run_decision_comparison` (Phase 9),
`run_optimization_analysis` (Phase 10 thin adapter, decision C5 — four
objectives only, solver status is vocabulary not advice; see
[docs/optimization-engine.md §17](optimization-engine.md)).

**Declarations (3, `executable=False`, `requires_approval=True`)** — no handler,
no execution path; creating one twice for the same key → 409:
`procurement_order_change`, `inventory_adjustment`, `scenario_deployment`.

`registry.list(category="mutation") == []` is asserted by tests. Tools that do
**not** exist (decision C2): `rank_options`, `get_recommendation`,
`compare_decisions`, and the other draft-era names listed in
[ai-assistant-design.md](ai-assistant-design.md).

## 5. Guardrails (code, not prompts)

- **Input**: parametrized injection patterns blocked before the provider
  (instruction override, table dumps, `DROP TABLE`/`delete from`, code execution,
  "unrestricted AI" role claims). Normal supply-chain asks pass.
- **Output**: banned-word scrub — `best`, `should`, `recommend*`, `ranked`,
  `preferred`, `top choice` — plus key-shape redaction and runaway-text
  truncation; an all-removed result falls back to a safe text.
- **No execution**: only registered handlers run; declarations have no handler;
  no SQL/Python generation anywhere in the pipeline.
- **No decision authority**: approvals record a human decision only;
  `executed` is a constant `false`.
- **Labeling**: evidence labels enum-validated; compute reports forced to
  `simulated`; assistant turns `derived`.
- **Bounded context**: history capped (`AI_MAX_HISTORY_MESSAGES`, default 12)
  with an explicit truncation marker in the prompt context.

## 6. Providers

```
ENABLE_AI_ASSISTANT=false (default) → MockProvider (deterministic, offline)
ENABLE_AI_ASSISTANT=true + AI_PROVIDER=mock    → MockProvider
ENABLE_AI_ASSISTANT=true + AI_PROVIDER=openai  → HttpOpenAIProvider
    (requires OPENAI_API_KEY; httpx only; AI_MODEL, AI_REQUEST_TIMEOUT_SECONDS)
anything else → ProviderConfigurationError → 503 AI_UNAVAILABLE (no silent fallback)
```

- MockProvider returns a valid plan/synthesis offline; `describe()` never
  exposes the key.
- HttpOpenAIProvider retries transient errors (429/5xx/transport) with bounded
  backoff, fails fast on 400, and turns malformed bodies into 503.
- No `openai`/`google` SDKs, no `tenacity`, no Redis (decision C7).

## 7. Rate limits (decision C6)

| Tier | Per hour | Per day |
|---|---|---|
| analyst | 100 | 1000 |
| planner | 200 | 2000 |
| manager | 500 | 5000 |
| executive | 500 | 5000 |
| admin | unlimited | unlimited |

Sliding windows per user (`InMemoryRateLimiter`, process-local). Denials return
429 + `Retry-After` (seconds until the oldest hit ages out) and an audit row.
The limiter fails open on internal fault; authentication always fails closed.

## 8. Persistence and audit

- `ai_conversations` (label `user-provided`), `ai_messages` (user
  `user-provided`, assistant `derived`, with `intent`, `confidence`,
  `tool_calls`, `provider`, `model`, `sequence`), `ai_approvals` (label
  `derived`; JSONB `declaration`; `status` pending/approved/rejected).
- `audit_events` actions: `ai.chat`, `ai.tool.call`, `ai.approval.decision`,
  `ai.ratelimit.exceeded` — append-only, bounded JSON parameters, never secrets;
  unauthenticated failures are logged but never fabricated into the trail.

## 9. Configuration reference

| Setting | Default | Meaning |
|---|---|---|
| `ENABLE_AI_ASSISTANT` | `false` | Feature gate; false ⇒ MockProvider |
| `AI_PROVIDER` | `openai` | `mock` or `openai` when enabled |
| `AI_MODEL` | `gpt-4o-mini` | Cloud model name |
| `AI_REQUEST_TIMEOUT_SECONDS` | `30.0` | httpx timeout |
| `AI_MAX_HISTORY_MESSAGES` | `12` | History bound (oldest dropped first) |
| `AI_MAX_TOOL_CALLS_PER_TURN` | `8` | Per-turn executor cap |

## 10. Testing

103 tests in 7 files (`test_ai_{api,guardrails,ratelimit,provider,registry,tools,service}.py`),
all green; full repository regression **768 passed, 0 failed**. Coverage details:
[docs/testing-strategy.md](testing-strategy.md) §Phase 11. Patterns: shared
`ai_client` fixture (httpx `ASGITransport` + `get_db` dependency override),
provider/limiter stubs via FastAPI `dependency_overrides`, synthetic fixtures
only, org-isolation test with a second generated organization.

## 11. Known limitations

- The limiter is process-local: limits reset on restart and are not shared
  across workers (no Redis by decision C6).
- The intent classifier is a deterministic keyword heuristic — its confidence
  is a documented offline heuristic, not a calibrated statistic.
- MockProvider is rule-based; switching to a cloud model changes answer
  quality but not the guardrail, contract, or audit behavior (all enforced in
  code).
- Approval declarations are records only: nothing in the platform executes a
  decided action; wiring execution is out of scope for Phase 11.
