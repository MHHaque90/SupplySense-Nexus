# Product Requirements: SupplySense Nexus

## Product Vision

SupplySense Nexus is an AI-powered supply chain resilience and decision intelligence platform. It enables supply-chain teams to anticipate disruptions, evaluate alternatives, and make informed procurement decisions backed by data, models, and transparent reasoning.

The central differentiator is **disruption-aware procurement decision intelligence**: the ability to simulate disruptions, compare operational responses, and recommend the best action balancing cost, service, and risk.

## Target Users

- **Supply-Chain Analyst**: Uses forecasting, scenario analysis, and data-quality tools to plan demand and inventory.
- **Procurement Manager**: Evaluates supplier performance, alternatives, and procurement recommendations under constraints.
- **Inventory Planner**: Monitors stock positions, safety stock, stockout risk, and days of supply.
- **Operations Manager**: Oversees warehouse capacity, allocation, and disruption response strategies.
- **Business Analyst**: Runs backtests, monitors model drift, and generates governance reports.
- **Executive Decision-Maker**: Reviews portfolio-level risk exposure, service levels, and financial impact summaries.

## Primary Business Problems

1. **Supplier Disruptions**: A delayed or failed supplier cascades through the supply chain with unclear impact.
2. **Inventory Mismanagement**: Too much stock ties up working capital; too little creates stockout risk.
3. **Demand Uncertainty**: Forecasts lack uncertainty estimates, leading to poor planning.
4. **Opaque Decision-Making**: Decisions are made without comparing alternatives or tracking assumptions.
5. **Limited Scenario Planning**: Teams cannot evaluate "what-if" scenarios systematically.
6. **Supplier Concentration Risk**: Over-reliance on a single supplier creates vulnerability.
7. **Lack of Reproducibility**: Decisions cannot be replayed, audited, or compared against outcomes.

## User Personas

### Persona 1: Priya - Supply-Chain Analyst
- Uses historical demand data to create forecasts.
- Needs prediction intervals and model drift alerts.
- Works with Python or a web dashboard.

### Persona 2: Carlos - Procurement Manager
- Evaluates supplier performance and alternatives.
- Needs optimization under MOQ, budget, and capacity constraints.
- Requires cost comparison across decision options.

### Persona 3: Emily - Inventory Planner
- Monitors current inventory position across warehouses.
- Needs safety stock calculations and stockout risk estimates.
- Requires days-of-supply and working-capital exposure metrics.

### Persona 4: David - Operations Manager
- Manages warehouse capacity and allocation.
- Needs disruption impact mapping across the network.
- Requires reallocation recommendations during disruptions.

### Persona 5: Sarah - Executive Decision-Maker
- Reviews portfolio-level risk and financial impact.
- Needs confidence levels and recommendation rationale.
- Requires audit trails and governance reports.

## Core Workflows

### Workflow 1: Demand Forecasting
1. Load historical demand data.
2. Run data-quality checks.
3. Train baseline and ML forecasting models.
4. Generate forecasts with prediction intervals.
5. Compare models using time-based validation.
6. Monitor for drift.

### Workflow 2: Disruption Response
1. Detect or simulate a disruption event.
2. Map impact through the supply-chain risk graph.
3. Generate decision options (wait, expedite, reallocate, substitute).
4. Simulate each option's financial, service, and risk impact.
5. Compare alternatives in the Decision Replay Lab.
6. Rank recommendations with confidence levels.
7. Obtain human approval before action.

### Workflow 3: Procurement Optimization
1. Identify demand forecast and inventory position.
2. Apply constraints (MOQ, budget, capacity, lead-time).
3. Run multi-objective optimization.
4. Present Pareto-optimal options.
5. Document assumptions and data sources.
6. Require human approval for consequential procurement.

### Workflow 4: AI-Assisted Analysis
1. User asks a natural-language question.
2. Intent is classified.
3. Controlled tools retrieve evidence.
4. Response includes references, confidence, and limitations.
5. Audit log records the query and response.
6. Human approval required for consequential actions.

## Functional Requirements

### Data Foundation
- FR-01: Ingest sales, product, inventory, supplier, and shipment data.
- FR-02: Validate data quality with configurable rules.
- FR-03: Track data lineage and source labeling.
- FR-04: Support public, synthetic, user-provided, derived, and simulated data labels.

### Demand Intelligence
- FR-05: Generate forecasts using baseline and ML models.
- FR-06: Provide prediction intervals and uncertainty estimates.
- FR-07: Compare forecast models with error metrics.
- FR-08: Detect and report model drift.
- FR-09: Provide forecast explainability features.

### Inventory Intelligence
- FR-10: Report current inventory position (available, reserved, in-transit).
- FR-11: Calculate safety stock, reorder points, and days of supply.
- FR-12: Estimate stockout risk and overstock risk.
- FR-13: Analyze inventory turnover and working-capital exposure.

### Supplier and Procurement Intelligence
- FR-14: Generate supplier scorecards (delivery, quality, cost, lead-time).
- FR-15: Analyze supplier concentration and single-source dependency.
- FR-16: Calculate total cost of ownership.
- FR-17: Recommend alternative suppliers.
- FR-18: Optimize procurement quantities under constraints.

### Supply-Chain Risk Graph
- FR-19: Map supplier-to-component-to-product-to-warehouse relationships.
- FR-20: Identify critical components and single points of failure.
- FR-21: Propagate disruption impacts through the dependency graph.

### Disruption and Scenario Lab
- FR-22: Define and simulate disruption scenarios.
- FR-23: Support combined disruptions.
- FR-24: Generate impact reports with sensitivity analysis.

### Decision Replay Lab
- FR-25: Define baseline and alternative scenarios.
- FR-26: Compare decisions across cost, service, risk, and inventory dimensions.
- FR-27: Present decision options with factual deltas and confidence scores (no rankings, no recommendations — options and trade-off quantities are surfaced for the human decision-maker).
- FR-28: Track assumptions and reproducibility metadata.

### Optimization Engine
- FR-29: Optimize supplier selection and procurement quantity.
- FR-30: Enforce budget, capacity, MOQ, lead-time, and service-level constraints.
- FR-31: Perform multi-objective trade-off analysis.

### AI Decision Copilot
- FR-32: Accept natural-language questions.
- FR-33: Classify intent and route to controlled tools.
- FR-34: Retrieve evidence and present with references.
- FR-35: Express uncertainty and limitations explicitly.
- FR-36: Require human approval for consequential decisions.

### Governance and Evaluation
- FR-37: Generate data-quality reports.
- FR-38: Maintain model registry with versioning.
- FR-39: Run backtests and monitor drift.
- FR-40: Maintain audit logs and decision traceability.

## Non-Functional Requirements

- **Performance**: API responses under 500ms for standard queries (95th percentile).
- **Scalability**: Support up to 1M demand observations and 100K inventory records.
- **Reliability**: 99.9% uptime for core APIs; graceful degradation for AI features.
- **Security**: No SQL injection; API key-based authentication; role-based access control.
- **Maintainability**: Clear code structure; comprehensive tests; documented APIs.
- **Reproducibility**: All forecasts, simulations, and optimizations must be reproducible with seeds.
- **Transparency**: All AI responses must cite evidence and express uncertainty.

## MVP Boundary

**In MVP (Phase 1-3)**:
- PostgreSQL schema with core entities
- Data ingestion and quality validation
- Baseline forecasting (naive, seasonal naive, moving average)
- Inventory position reporting
- Supplier scorecards
- Basic scenario definition

**Not in MVP**:
- ML forecasting models (Phase 4)
- Optimization engine (Phase 10)
- AI Decision Copilot (Phase 11)
- Full frontend dashboard (Phase 12)
- Decision Replay Lab (Phase 9)

## Full-Platform Boundary

**Full Platform (Phase 0-11)** includes all modules A through J from the product specification.

## Explicit Non-Goals

- **No Kubernetes**: Not needed for portfolio-scale deployment.
- **No Kafka**: Event streaming is unnecessary at this scale.
- **No reinforcement learning**: Use statistical and optimization methods instead.
- **No graph database**: Relational representation suffices initially.
- **No multi-agent orchestration**: Single AI assistant with controlled tools.
- **No paid external services**: All data processing is self-hosted.
- **No real company data**: Use synthetic or clearly licensed public data.

## Assumptions

1. PostgreSQL 17 is available and running.
2. Python 3.12+ is available for the backend.
3. Data will be synthetic or from clearly licensed public sources.
4. Users have basic supply-chain domain knowledge.
5. The platform operates in a single organization initially.
6. Forecasting uses daily or weekly granularity.
7. All simulated outputs are labeled clearly.

## Risks

1. **Data Quality**: Synthetic data may not capture real-world variability.
2. **Model Accuracy**: Baseline models may have high error for complex demand patterns.
3. **Scope Creep**: The platform has many modules; discipline is required to stay phased.
4. **AI Reliability**: LLM-based copilot may hallucinate; guardrails are essential.
5. **Performance**: Large datasets may require optimization before scaling.
6. **Dependency Management**: Third-party library updates may break compatibility.

## Success Criteria

1. All Phase 0 deliverables are documented and reviewed.
2. The FastAPI backend starts and serves health endpoints.
3. The database schema is defined and documented.
4. Tests pass for the health endpoint.
5. The frontend loads correctly.
6. Documentation covers all modules A through J.
7. AGENTS.md provides clear coding standards.

## Portfolio Demonstration Goals

1. **Engineering Quality**: Clean architecture, comprehensive documentation, testing strategy.
2. **End-to-End Vision**: Demonstrate understanding of the full platform lifecycle.
3. **Technical Depth**: Show sophisticated design without premature implementation.
4. **Data Integrity**: Clear labeling of synthetic vs. real data throughout.
5. **Safety Focus**: AI guardrails, audit trails, human approval workflows.
6. **Practical Phasing**: Realistic roadmap with verifiable checkpoints.
