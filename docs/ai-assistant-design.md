# AI Decision Copilot Design: SupplySense Nexus

## Overview

The AI Decision Copilot provides natural-language interaction with the SupplySense Nexus platform. It uses a cloud LLM API (replaceable provider) with a controlled tool-calling architecture to deliver evidence-backed, auditable responses.

## Assistant Responsibilities

1. **Analytical Querying**: Answer supply-chain questions using read-only tools.
2. **Scenario Guidance**: Help users define and evaluate scenarios.
3. **Decision Comparison**: Explain trade-offs between decision options.
4. **Assumption Clarification**: Identify and explain assumptions behind recommendations.
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
| `assumption_explanation` | Ask about assumptions | "What assumptions are behind this recommendation?" |
| `data_quality` | Ask about data quality | "What data quality issues exist?" |
| `general_inquiry` | General platform questions | "How does the Decision Replay Lab work?" |

## Tool Registry Design

### Tool Interface
```python
class Tool(BaseModel):
    name: str
    description: str
    input_schema: dict  # Pydantic model schema
    output_schema: dict
    read_only: bool
    requires_approval: bool
    category: str
```

### Tool Registry
- All tools are registered in a central registry.
- The AI assistant can only call registered tools.
- Tool outputs are validated before being passed to the LLM.

### Read-Only Analytical Tools

| Tool | Description | Input | Output |
|------|-------------|-------|--------|
| `get_forecast` | Retrieve product forecast | product_id, horizon | Forecast with intervals |
| `get_inventory_position` | Get current inventory | warehouse_id, product_id | Inventory levels |
| `get_stockout_risk` | Estimate stockout risk | product_id, warehouse_id | Risk probability |
| `get_supplier_scorecard` | Get supplier metrics | supplier_id | Scorecard data |
| `get_scenario_results` | Retrieve scenario outcomes | scenario_id | Results and comparison |
| `list_scenarios` | List existing scenarios | filters | Scenario list |
| `get_data_quality_report` | Get data quality metrics | table_name | Quality metrics |
| `get_demand_observations` | Retrieve historical demand | product_id, date_range | Demand data |

### Scenario Tools

| Tool | Description | Input | Approval Required |
|------|-------------|-------|-------------------|
| `create_scenario` | Define a new scenario | scenario parameters | No (read-only) |
| `simulate_scenario` | Run Monte Carlo simulation | scenario_id, iterations | No |
| `evaluate_decision` | Evaluate a decision option | scenario_id, option_type | No |

### Decision Comparison Tools

| Tool | Description | Input | Approval Required |
|------|-------------|-------|-------------------|
| `compare_decisions` | Compare multiple options | scenario_id, option_ids | No |
| `rank_options` | Rank decision options | scenario_id, weights | No |
| `get_recommendation` | Get ranked recommendation | scenario_id | No |

### Approval-Required Tools (Mutating)

| Tool | Description | Input | Rationale |
|------|-------------|-------|-----------|
| `approve_procurement` | Approve a procurement action | order_id, details | Consequential action |
| `apply_scenario` | Apply scenario to production data | scenario_id | Changes actual data |
| `update_inventory` | Adjust inventory records | adjustments | Changes actual data |

## Guardrails

1. **No Arbitrary SQL**: The AI assistant never generates or executes SQL.
2. **No Arbitrary Python**: The AI assistant never generates or executes Python code.
3. **No Procurement Modification**: The AI assistant cannot modify procurement records without explicit human approval.
4. **No Purchase Approval**: The AI assistant cannot approve purchases.
5. **No Uncertainty Hiding**: All responses include confidence levels and limitations.
6. **No Synthetic Data Mislabeling**: Simulated results are always labeled as simulated.
7. **No Fabrication**: The AI assistant never invents analytical results.
8. **Tool Constraint**: Only registered tools can be called.
9. **Rate Limits**: Per-user rate limits prevent abuse.
10. **Content Filtering**: Responses are filtered for inappropriate content.

## Prompt Construction

### System Prompt Template
```
You are SupplySense Nexus AI Assistant. You help supply-chain professionals 
make informed decisions by retrieving and analyzing data from the platform.

Key rules:
- Always cite data sources and their labels (public, synthetic, simulated)
- Express uncertainty when confidence is below 0.70
- Never execute SQL or Python code
- Never approve purchases or modify procurement records
- Clearly label all simulated/estimated outputs
- If you don't have sufficient evidence, say so explicitly
- All consequential decisions require human approval
```

### Context Construction
1. **User Query**: The natural-language question.
2. **Intent Classification**: Result from the intent classifier.
3. **Tool Results**: Outputs from called tools (evidence).
4. **Historical Context**: Previous conversation turns (for multi-turn).
5. **Current Scenario**: Active scenario context if applicable.

### Tool Call Format
```
The LLM is prompted to produce tool calls in a structured format:

{"tool": "get_forecast", "parameters": {"product_id": "prod-123", "horizon": 30}}
```

The tool executor validates the call, runs the tool, and returns results.
Results are appended to the context for the LLM to synthesize a response.

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

1. **Authentication**: Every request includes a valid API key.
2. **Authorization**: User role determines accessible data and tools.
3. **Organization**: Users can only access data within their organization.
4. **Tool Permissions**: Some tools require specific roles (e.g., manager for procurement).
5. **Approval Workflow**: Mutating actions require explicit human approval.

## Audit Logging

Every AI interaction is logged:
- User ID and role
- Query text
- Intent classification
- Tools called and parameters
- Tool outputs
- Response generated
- Confidence score
- Timestamp
- Session ID

Audit logs are append-only and immutable.

## Rate Limits

| Tier | Requests per Hour | Requests per Day |
|------|-------------------|------------------|
| Analyst | 100 | 1000 |
| Planner | 200 | 2000 |
| Manager | 500 | 5000 |
| Executive | 500 | 5000 |
| Admin | Unlimited | Unlimited |

Rate limits prevent abuse and ensure fair resource usage.

## Failure Handling

1. **LLM Unavailable**: Return "Service temporarily unavailable. Please try again later."
2. **Tool Failure**: Return error message with affected tool name.
3. **Invalid Intent**: Ask for clarification with suggested intents.
4. **Insufficient Evidence**: State clearly that evidence is insufficient.
5. **Partial Results**: Present available evidence and note gaps.
6. **Timeout**: Return partial results with a note about incomplete analysis.

## Human Approval Requirements

The following actions require explicit human approval:
- Procurement order changes
- Inventory adjustments
- Supplier contract modifications
- Scenario deployment to production
- Any action that modifies actual business data

The AI assistant presents the proposed action with:
- Description of the action
- Expected impact (cost, service, risk)
- Assumptions and data sources
- Confidence level
- **Approval button for human decision-maker**

## Example Interaction

**User**: "If Supplier A delays by 2 weeks, what should we do?"

**Assistant**:
1. Classify intent: `decision_comparison`
2. Call tools: `get_inventory_position`, `get_supplier_scorecard`, `list_scenarios`
3. Create scenario: "Supplier A 2-week delay"
4. Call tools: `simulate_scenario`, `compare_decisions`
5. Generate response:

"Based on analysis of the scenario 'Supplier A 2-week delay' (simulated):

**Recommended action**: Reallocate inventory from Warehouse X (Confidence: 78%)
- Estimated cost savings vs. waiting: $15,000
- Expected service level impact: -2% (from 96% to 94%)
- Stockout risk reduction: from 23% to 12%

**Alternatives**:
- Expedite: Higher cost ($65K) but better service (96%)
- Wait: Lowest cost ($50K) but highest risk (stockout 23%)

*Note: All results are simulated estimates based on synthetic data. This recommendation requires human approval before implementation.*"

**Audit log**: Full interaction logged with all tool calls, outputs, and response.
