# AI Decision Copilot Design: SupplySense Nexus

## Overview

The AI Decision Copilot provides natural-language interaction with the SupplySense Nexus platform. It uses a pluggable LLM provider abstraction with a controlled tool-calling architecture to deliver evidence-backed, auditable responses. By default it runs the deterministic **MockProvider** (no API key, no network: `ENABLE_AI_ASSISTANT=false`). Enabling `ENABLE_AI_ASSISTANT=true` selects the provider named by `AI_PROVIDER` — `"mock"` or `"openai"` (an OpenAI-compatible endpoint via an httpx-only HTTP client, requires `OPENAI_API_KEY`); a misconfigured provider surfaces as 503 `AI_UNAVAILABLE`, never a silent fallback. Prompts are an additional layer only — every guardrail is also enforced in code (registry, executor, guardrails, approval service).

## Assistant Responsibilities

1. **Analytical Querying**: Answer supply-chain questions using read-only tools.
2. **Scenario Guidance**: Help users define and evaluate scenarios.
3. **Decision Comparison**: Explain trade-offs between decision options.
4. **Assumption Clarification**: Identify and explain the assumptions behind decision options.
5. **Evidence Presentation**: Cite data sources, models, and metrics.
6. **Uncertainty Communication**: Clearly express confidence and limitations.
7. **Audit and Compliance**: Log all interactions for governance.

## Intent Categories

| Intent | Description | Example |
|--------|-------------|---------|
| `demand_forecast` | Ask about demand predictions | "What's the forecast for Product A next month?" |
| `inventory_risk` | Ask about stockout or overstock risk | "Which products are at risk of stockout?" |
| `supplier_score` | Ask about supplier performance | "How reliable is Supplier B?" |
| `scenario_creation` | Create or modify a scenario | "Create a scenario where Supplier C delays by 2 weeks" |
| `decision_comparison` | Compare decision options | "Compare waiting vs. expediting for Scenario 1" |
| `assumption_explanation` | Ask about assumptions | "What assumptions are behind these numbers?" |
| `data_quality` | Ask about data quality | "What data quality issues exist?" |
| `general_inquiry` | General platform questions | "How does the Decision Replay Lab work?" |

## Tool Registry Design

### Tool Interface

```python
class ToolSpec:
    name: str
    description: str
    category: str          # read_only_analytics | simulation | decision_replay |
                           # optimization | approval_required | mutation
    parameters: dict       # JSON Schema for the input
    handler: Callable      # the only code path that can run
    required_roles: tuple[str, ...] = ()
    executable: bool = True
    requires_approval: bool = False
```

### Tool Registry

- All tools are registered in a central registry; the assistant can only call registered tools.
- Tool outputs are validated before being passed to the LLM.
- Declarations (`executable=False`) can only be created through `POST /ai/chat`; creating one twice for the same key returns 409.
- The `mutation` category exists but **must stay empty**: `registry.list(category=MUTATION) == []` is asserted by tests — no executable mutating tool may ever be registered.

### Read-Only Analytical Tools (7)

| Tool | Description | Data label |
|------|-------------|------------|
| `get_forecast` | Retrieve product forecast with intervals | `forecast` |
| `get_inventory_position` | Current inventory levels by warehouse/product | `synthetic` |
| `get_inventory_health` | Health metrics for inventory positions | `synthetic` |
| `get_supplier_scorecard` | Supplier performance scorecard | `synthetic` |
| `get_inventory_kpis` | Inventory KPI aggregates | `synthetic` |
| `get_data_quality_report` | Data-quality metrics per table | `derived` |
| `get_risk_report` | Disruption risk report | `synthetic` |

### Compute Tools (3, outputs labeled `simulated`)

| Tool | Category | Description |
|------|----------|-------------|
| `run_disruption_simulation` | simulation | Monte Carlo disruption impact (Phase 8) |
| `run_decision_comparison` | decision_replay | Factual decision comparison, constraint-checked (Phase 9) |
| `run_optimization_analysis` | optimization | Thin adapter over the Phase 10 MILP engine (objectives: cost, service_level, inventory_investment, disruption_risk — no silent weights, no re-ranking) |

### Approval-Required Declarations (3, `executable=False`)

| Declaration | Rationale |
|-------------|-----------|
| `procurement_order_change` | Consequential procurement action |
| `inventory_adjustment` | Changes actual business data |
| `scenario_deployment` | Promotes a scenario to production |

Declarations only create a pending `AiApproval` record surfaced through `POST /ai/approval`. **Approvals never execute**: `ApprovalView.executed` is always `false`.

### Tools That Do Not Exist (decision C2)

The following names from earlier drafts are intentionally **not** part of the platform: `rank_options`, `get_recommendation`, `compare_decisions`, `get_stockout_risk`, `get_scenario_results`, `list_scenarios`, `get_demand_observations`, `create_scenario`, `simulate_scenario`, `evaluate_decision`, `approve_procurement`, `apply_scenario`, `update_inventory`. The copilot never ranks options or issues recommendations.

## Guardrails

1. **No Arbitrary SQL**: The AI assistant never generates or executes SQL.
2. **No Arbitrary Python**: The AI assistant never generates or executes Python code.
3. **No Procurement Modification**: The AI assistant cannot modify procurement records; it can only declare an action awaiting human approval.
4. **No Purchase Approval**: The AI assistant cannot approve purchases, and an approval decision never executes the action.
5. **No Ranking or Recommendations**: The assistant never issues rankings, "best/preferred/top choice" options, or "you should" guidance; it presents factual differences, trade-off quantities, assumptions, and uncertainties for the human to decide (decision C2; enforced by an output guardrail with a banned-word check).
6. **No Uncertainty Hiding**: All responses include confidence levels and limitations.
7. **No Synthetic Data Mislabeling**: Simulated results are always labeled as simulated; labels come from the `DataSourceLabel` enum, never free text.
8. **No Fabrication**: Every claim must be backed by tool evidence; the assistant never invents analytical results.
9. **Tool Constraint**: Only registered tools can be called; the mutation category stays empty.
10. **Rate Limits**: Per-role rate limits prevent abuse (429 + `Retry-After`; limiter fails open, auth fails closed).
11. **Secret Redaction**: Provider API keys and secrets are never echoed into responses, logs, or audit parameters.
12. **Prompt Injection Resistance**: Input that attempts to override these rules is refused and recorded in the reply's `limitations`.

## Prompt Construction

### System Prompt Template

```
You are SupplySense Nexus AI Assistant, the AI Decision Copilot for a
supply-chain resilience platform.

Hard rules (also enforced in code):
- You never execute SQL, Python, or shell commands; only registered tools run.
- You never modify business data, approve purchases, or mutate inventory,
  procurement, suppliers, or shipments. Consequential actions are declared
  and require an explicit human approval decision; approving never executes.
- You never rank options or issue recommendations; you present factual
  differences, trade-off quantities, assumptions, and uncertainties and let
  the human decide.
- Every claim must be backed by tool evidence; never invent numbers.
- Always carry data labels (public, synthetic, user-provided, derived,
  simulated) into your answer; simulated results are labeled simulated.
- State confidence and limitations honestly; ask for clarification when
  evidence is insufficient.
```

The same rules are re-enforced in code; the prompt never carries user data or secrets.

### Context Construction
1. **User Query**: The natural-language question.
2. **Intent Classification**: Result from the intent classifier.
3. **Tool Results**: Outputs from called tools (evidence).
4. **Historical Context**: Previous conversation turns (for multi-turn).
5. **Current Scenario**: Active scenario context if applicable.

### Tool Call Format

```
The LLM is prompted to respond with a single JSON object:

{"intent": "inventory_risk",
 "tool_calls": [{"tool": "get_inventory_position", "parameters": {...}}],
 "response": "<assistant text for the user>",
 "confidence": 0.82}
```

Round 1 collects intent + tool plan; round 2 synthesizes the final answer over
`TOOL_RESULTS` (echoed values only). The tool executor validates the call
against the registry, runs the tool, and returns results. Calls naming
unregistered tools are refused and recorded in the reply's `limitations`.

## Evidence Handling

### Evidence Requirements
1. **Source**: Where the data came from (table, model, scenario).
2. **Label**: Data source label (public, synthetic, simulated).
3. **Timestamp**: When the data was generated.
4. **Confidence**: Statistical confidence of the underlying data.
5. **Limitations**: Known issues or constraints with the data.

### Evidence Presentation
```
Based on the forecast model "Holt-Winters v2.1" (trained 2026-08-15), 
Product A is expected to have demand of 1,200 units ± 150 units (95% interval) 
for the next 30 days.

- Source: demand_observations table
- Data label: synthetic (generated from historical patterns)
- Model confidence: 0.82
- Limitations: Does not account for upcoming holiday promotions
```

## Uncertainty Handling

### Confidence Scoring
- **High**: ≥ 0.80 - "The forecast indicates..."
- **Medium**: 0.60-0.79 - "Based on available data, the forecast suggests..."
- **Low**: < 0.60 - "There is insufficient data to provide a reliable estimate..."

### When to Express Uncertainty
1. Forecast intervals are wide.
2. Data quality is below threshold.
3. Model has not been validated for this product category.
4. Simulation sample size is small.
5. Assumptions are speculative or unverified.

### Language Patterns
- Instead of "Demand will be 1000 units" → "The forecast projects approximately 1000 units (80% interval: 850-1150)"
- Instead of "Supplier B is reliable" → "Based on historical data, Supplier B has a 95% on-time delivery rate over the past 12 months"

## Permission Checks

1. **Authentication**: Every request (except health) includes a valid opaque `Bearer ssk_...` API key; the server stores only its SHA-256 hash and compares with `hmac.compare_digest`. Missing, malformed, unknown, or deactivated keys all fail closed with the same 401 (`UNAUTHORIZED` / "Authentication failed.").
2. **Authorization**: User role determines accessible tools: chat and tool listing require analyst or above; approval decisions require manager, executive, or admin (admin bypasses role checks).
3. **Organization**: Users can only access data within their organization (tool queries are always scoped by `AuthContext.organization_id`).
4. **Identity Source**: Identity comes only from the authenticated principal — never from the request body or headers like `X-User-Id`.
5. **Approval Workflow**: Declared consequential actions require an explicit human approval decision; the decision is recorded but never executed.

## Audit Logging

Every AI interaction is logged append-only to the existing `audit_events` table:

- `ai.chat` — one row per chat request (intent, tools, confidence, provider, conversation).
- `ai.tool.call` — one row per executed (or refused) tool call.
- `ai.approval.decision` — one row per approve/reject decision.
- `ai.ratelimit.exceeded` — one row per denied request.

Each row carries user ID and role, timestamp, session ID, and bounded JSON
parameters that never contain raw API keys or provider secrets. Unauthenticated
failures (no `user_id` available) are recorded only in the application log —
never fabricated into the audit trail. Conversation turns are additionally
persisted to `ai_conversations` / `ai_messages` with the full history bounded
to a configurable maximum (oldest turns are dropped first).

Audit logs are append-only and immutable.

## Rate Limits

| Tier | Requests per Hour | Requests per Day |
|------|-------------------|------------------|
| Analyst | 100 | 1000 |
| Planner | 200 | 2000 |
| Manager | 500 | 5000 |
| Executive | 500 | 5000 |
| Admin | Unlimited | Unlimited |

Exceeding a limit returns 429 `RATE_LIMIT_EXCEEDED` ("Rate limit exceeded. Try
again later.") with a `Retry-After` header and an `ai.ratelimit.exceeded` audit
row. Counting is in-process (no Redis): the limiter **fails open** on internal
error (availability), while authentication **fails closed** (security).

## Failure Handling

1. **LLM Unavailable**: After bounded retries with backoff, return 503 `AI_UNAVAILABLE` ("AI service temporarily unavailable.") — never fabricate an answer.
2. **Tool Failure**: Return a reply whose `limitations` name the affected tool; tool errors are surfaced as "Tool execution failed." without internal details.
3. **Invalid/Empty Intent**: Default to `general_inquiry` and ask for clarification with the supported intent list.
4. **Insufficient Evidence**: State clearly that evidence is insufficient in `limitations`.
5. **Partial Results**: Present available evidence and note gaps.
6. **Rate Limited**: 429 with `Retry-After`.
7. **Guardrail Violation (output)**: The reply is rewritten/flagged by the governance scrubber; the violation is recorded in `limitations`.

## Human Approval Requirements

The following actions can only be **declared** by the copilot (they are never executed by it):
- Procurement order changes
- Inventory adjustments
- Scenario deployment to production

The declaration stores a pending `AiApproval` record (action, rationale,
evidence refs, status `pending`) surfaced through the response's `approval_ids`
meta. The human decision is submitted via `POST /ai/approval` (manager+):
`decision: "approve" | "reject"`. Whatever the decision, `executed` stays
`false` — recording a decision is the entire effect; an "approve" does not run
the action.

The assistant presents the declared action with:
- Description of the action
- Quantified impact observations (cost, service, risk)
- Assumptions and data sources
- Confidence level
- Pending status awaiting the human decision-maker

## Example Interaction

**User**: "If Supplier A delays by 2 weeks, what should we do?"

**Assistant**:
1. Classify intent: `decision_comparison`
2. Round 1 tool plan: `get_inventory_position`, `get_supplier_scorecard`, `run_disruption_simulation`
3. Round 2 synthesis over `TOOL_RESULTS`:

"Analysis of a 2-week Supplier A delay (all figures simulated):

**Observable differences between the declared options:**
- Expedite: +$65K estimated cost, service level 96% (simulated)
- Wait: baseline cost $50K, stockout risk rises from 23% to 12% (simulated)

**Assumptions**: delay duration fixed at 14 days; no alternate supplier.
**Confidence**: 0.74 — driven by historical on-time rates (synthetic data, 12-month window).
**Limitations**: does not model promotion demand.

*All results are simulated estimates based on synthetic data. Options are presented
with factual differences only; the decision is yours. One declared action is
pending approval (approval_id in meta).*"

**Audit log**: `ai.chat` + one `ai.tool.call` row per tool, full interaction logged.

---

*Implementation reference: `backend/app/ai/` (service, intents, prompts, guardrails, ratelimit, audit, approvals) and `backend/app/ai/tools/` (13 registered tools), served by `backend/app/api/ai_router.py`. Full operational contract in [docs/ai-decision-copilot.md](ai-decision-copilot.md).*
