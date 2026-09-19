# Decision Engine Design: SupplySense Nexus

## Overview

The Decision Replay Lab is the central innovation of SupplySense Nexus. It allows users to compare multiple operational decisions under the same disruption scenario and receive ranked recommendations with confidence scores.

## Design Principles

1. **Reproducibility**: All scenarios and results are reproducible with fixed seeds and stored parameters.
2. **Transparency**: Every recommendation includes its assumptions, data sources, and model confidence.
3. **Simulation Labels**: All simulated results are explicitly labeled as simulated, estimated, or illustrative.
4. **Multi-Objective**: Trade-offs between cost, service level, and risk are explicitly quantified.
5. **Human-in-the-Loop**: Recommendations require human approval before consequential actions.

## Scenario Input Model

A scenario defines the conditions under which decisions are evaluated.

| Field | Type | Description |
|-------|------|-------------|
| name | string | Human-readable scenario name |
| description | text | Detailed scenario description |
| scenario_type | enum | baseline, alternative, combined |
| disruption_events | list | Events that define the scenario |
| base_assumptions | json | Global assumptions (demand, lead times, costs) |
| created_by | UUID | User identifier |
| data_source_label | string | simulated |

**Base assumptions include**: base demand forecast, current inventory levels, supplier lead times, unit costs, and capacity constraints.

## Scenario Event Model

Events define specific disruptions within a scenario.

| Field | Type | Description |
|-------|------|-------------|
| event_type | enum | supplier_delay, supplier_failure, demand_spike, demand_drop, transport_disruption, warehouse_capacity_reduction, component_shortage, cost_increase, tariff_shock, lead_time_variation |
| magnitude | decimal | Severity of the event |
| duration_days | int | How long the event lasts |
| affected_entity_id | UUID | Supplier, product, or warehouse |
| probability | decimal | Probability of occurrence |
| data_source_label | string | simulated |

**Example**: `{ event_type: "supplier_delay", magnitude: 0.3, duration_days: 14, affected_entity_id: "supplier-abc", probability: 0.8 }`
- Meaning: 30% increase in lead time for 14 days, 80% probability.

## Decision Option Model

Each decision option represents an operational response to a scenario.

| Field | Type | Description |
|-------|------|-------------|
| option_type | enum | wait, alternative_supplier, expedite, reallocate, reduce_demand, split_po, change_qty, delay_commitments |
| description | text | Human-readable description |
| parameters | json | Decision-specific parameters |
| estimated_cost | decimal | Estimated financial impact |
| estimated_service_level | decimal | Estimated service level |
| estimated_stockout_risk | decimal | Estimated stockout probability |
| data_source_label | string | simulated |

### Decision Option Types

1. **Wait**: Do nothing and wait for original supplier.
2. **Alternative Supplier**: Switch to a pre-identified alternative supplier.
3. **Expedite**: Pay premium for faster delivery from current supplier.
4. **Reallocate**: Move inventory from other warehouses.
5. **Reduce Demand**: Allocate limited supply to high-priority customers.
6. **Split PO**: Split order across multiple suppliers.
7. **Change Quantity**: Adjust order quantity based on updated demand forecast.
8. **Delay Commitments**: Push back delivery dates to customers.

## Cost Model

Costs are estimated for each decision option using the following components:

### Direct Costs
- **Unit Cost**: Purchase cost at supplier unit price.
- **Shipping Cost**: Transportation and logistics costs.
- **Expedite Premium**: Additional cost for faster fulfillment.

### Indirect Costs
- **Stockout Cost**: Lost sales and goodwill impact per unit short.
- **Holding Cost**: Inventory carrying cost per unit per day.
- **Penalty Cost**: Contractual penalties for late delivery.

### Total Cost Formula
```
Total Cost = Direct Costs + Indirect Costs + Disruption Impact Costs
```

All cost estimates are labeled as **simulated/estimated**.

## Service-Level Model

### Definition
Service level = Percentage of demand fulfilled on time and in full (OTIF).

### Calculation
```
Service Level = (Demand Fulfilled On Time) / (Total Demand)
```

### Factors
- Supplier lead time reliability
- Inventory availability at fulfillment points
- Demand volatility
- Decision option effectiveness

### Target Service Levels
- **Critical products**: ≥ 98%
- **Standard products**: ≥ 95%
- **Low-priority products**: ≥ 90%

## Risk Model

### Stockout Risk
Probability that demand exceeds available supply within the planning horizon.

```
Stockout Risk = P(Demand > Available Supply + In-Transit + Alternatives)
```

### Factors
- Demand uncertainty (from forecast intervals)
- Supply reliability (from supplier scorecards)
- Lead time variability
- Inventory buffer levels

### Risk Scoring
- **Low**: < 5% stockout probability
- **Medium**: 5-15% stockout probability
- **High**: > 15% stockout probability

## Inventory Impact Model

### Metrics
- **Days of Supply**: Current inventory divided by average daily demand.
- **Inventory Turnover**: Annual COGS divided by average inventory.
- **Working Capital Exposure**: Value of inventory tied up in stock.
- **Safety Stock**: Buffer to achieve target service level.
- **Reorder Point**: Inventory level triggering replenishment.

### Decision Impact
Each decision option affects inventory differently:
- **Wait**: Depletes inventory, increases stockout risk.
- **Reallocate**: Shifts inventory between locations.
- **Change Quantity**: Alters future inventory position.

## Constraint Model

### Types of Constraints
1. **MOQ (Minimum Order Quantity)**: Supplier-enforced minimum order size.
2. **Budget**: Maximum procurement spend.
3. **Capacity**: Warehouse or supplier capacity limits.
4. **Lead-Time**: Maximum acceptable lead time.
5. **Service-Level**: Minimum acceptable service level.

### Constraint Validation
- All decision options are checked against constraints.
- Violating options are flagged and ranked lower.
- Constraint violations are documented in results.

## Optimization Model

### Objective Functions
1. **Minimize Cost**: Minimize total procurement and disruption costs.
2. **Maximize Service**: Maximize OTIF service level.
3. **Multi-Objective**: Weighted combination of cost and service.

### Optimization Engine
- Uses OR-Tools for constraint optimization.
- Supports linear, integer, and mixed-integer programming.
- Generates Pareto-optimal solutions for multi-objective cases.

### Implementation
- Input: Decision variables, constraints, objective function.
- Solver: OR-Tools CP-SAT or linear solver.
- Output: Optimal solution with objective value and variable assignments.

## Simulation Model

### Monte Carlo Simulation
1. Define probability distributions for uncertain parameters.
2. Draw N random samples (e.g., N=10,000) using a fixed seed.
3. For each sample, evaluate all decision options.
4. Aggregate results to compute expected values and confidence intervals.

### Probability Distributions
- **Demand**: Normal or log-normal distribution based on forecast error.
- **Lead Time**: Normal distribution based on historical lead time variability.
- **Supplier Failure**: Bernoulli distribution based on historical failure rate.
- **Cost**: Triangular distribution based on min, most likely, max estimates.

### Reproducibility
- All simulations use `numpy.random.default_rng(seed=42)`.
- Seed is stored with the scenario.
- Results are deterministic given the same seed.

## Sensitivity Analysis

### Parameters Varied
- Demand growth rate (e.g., -20% to +20%)
- Lead time variability (e.g., ±50%)
- Cost assumptions (e.g., ±20% unit cost)
- Supplier reliability (e.g., 80% to 99% on-time)

### Method
- One-at-a-time (OAT) sensitivity analysis.
- Tornado diagrams to visualize parameter impact.
- Identify which assumptions most affect recommendations.

## Recommendation Ranking

### Scoring Formula
```
Composite Score = w_cost * normalized_cost + w_service * normalized_service + w_risk * normalized_risk
```

Where:
- `w_cost`, `w_service`, `w_risk` are user-defined weights (default: 0.4, 0.3, 0.3).
- Normalized values are scaled 0-1 across all options.
- Lower cost and risk are better; higher service is better.

### Ranking Process
1. Score all decision options using the composite formula.
2. Rank by composite score.
3. Calculate confidence score based on:
   - Simulation sample size
   - Consistency of results across scenarios
   - Data quality of inputs
   - Assumption stability
4. Generate recommendation rationale explaining the top choice.

### Confidence Calculation
```
Confidence = f(data_quality, sample_size, assumption_stability, model_consistency)
```

- **High Confidence**: > 0.80
- **Medium Confidence**: 0.60-0.80
- **Low Confidence**: < 0.60

## Assumption Tracking

Every scenario and decision comparison records:
1. **Data Sources**: Which datasets were used and their labels.
2. **Model Versions**: Which forecast models produced inputs.
3. **Random Seeds**: Seeds used for simulation reproducibility.
4. **Parameter Values**: All input parameter values.
5. **Temporal Context**: When the analysis was performed.
6. **User Context**: Who performed the analysis and their role.

## Reproducibility Requirements

1. **Seed-based**: Same seed + same data = same results.
2. **Configuration Snapshot**: All parameters stored with results.
3. **Version Tracking**: Data versions, model versions, and code versions recorded.
4. **Audit Trail**: All decision analyses are logged to the audit trail.
5. **Re-run Capability**: Scenarios can be re-run at any time with stored parameters.

## Example Scenario Walkthrough

**Scenario**: Supplier A (a key component supplier) has a 30% probability of a 14-day delay.

**Baseline**: Wait for original supplier.
**Alternatives**:
- Option B: Switch to Supplier B (higher unit cost, shorter lead time)
- Option C: Expedite current shipment
- Option D: Reallocate inventory from Warehouse X

**Assumptions** (all simulated):
- Demand during disruption: normally distributed, mean=1000, std=200
- Supplier B lead time: 5 days, unit cost 15% higher
- Expedite premium: 20% surcharge
- Reallocation cost: $2/unit

**Simulated Results** (illustrative):
- Wait: Cost=$50K, Service Level=87%, Stockout Risk=23%
- Alternative Supplier: Cost=$75K, Service Level=96%, Stockout Risk=5%
- Expedite: Cost=$65K, Service Level=93%, Stockout Risk=8%
- Reallocate: Cost=$35K, Service Level=91%, Stockout Risk=12%

**Recommendation**: Reallocate (rank 1) with 78% confidence.
- Rationale: Best balance of cost and service; moderate risk.
- **Note**: These results are simulated and illustrative.

**Sensitivity**: If demand variance increases to 400, expedite becomes preferred.

## Failure Handling

1. **Infeasible Solution**: If no option satisfies all constraints, report infeasibility with relaxed constraints.
2. **Simulation Failure**: If simulation fails, use point estimates with wider intervals.
3. **Data Gaps**: If data is missing for a product, use category-level averages with warning labels.
4. **Confidence Below Threshold**: If confidence < 0.50, present results as "insufficient evidence" and recommend data collection.
