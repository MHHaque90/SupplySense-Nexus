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

---

## Phase 4: Supplier and Procurement Intelligence

### Objectives
- Build supplier scorecards.
- Implement supplier performance analytics.
- Create alternative supplier analysis.
- Calculate total cost of ownership.
- Implement supplier concentration analysis.

### Deliverables
- Supplier scorecard generation
- Performance metrics aggregation (on-time delivery, quality, cost, lead-time)
- Alternative supplier analysis
- Total cost of ownership calculation
- Supplier concentration metrics (HHI, dependency analysis)
- Procurement recommendation engine (baseline)

### Dependencies
- Phase 3 complete.
- Supplier and purchase order data available.

### Risks
- Scorecard weighting may need business input to be useful.
- Alternative supplier data may be limited.

### Verification Checklist
- Supplier scorecards are generated correctly.
- Performance metrics are accurate.
- Alternative suppliers are identified and ranked.
- Concentration analysis identifies key dependencies.
- Procurement recommendations are generated with clear rationale.

### Definition of Done
- Supplier intelligence module is functional.
- All analytics are available via API.
- Recommendations include evidence and confidence levels.

---

## Phase 5: Risk Dependency Mapping

### Objectives
- Build supply-chain risk graph using relational representation.
- Identify critical components and single points of failure.
- Implement disruption impact propagation.
- Create dependency visualization.

### Deliverables
- Relational risk graph model
- Critical component identification algorithm
- Dependency propagation engine
- Risk impact reports
- Single-point-of-failure analysis

### Dependencies
- Phase 4 complete.
- Product, supplier, and BOM data available.

### Risks
- Relational representation may become complex for large networks.
- Propagation algorithm accuracy depends on data quality.

### Verification Checklist
- Risk graph correctly represents all dependencies.
- Critical components are identified.
- Disruption propagation produces expected results.
- Single-point-of-failure analysis identifies true vulnerabilities.
- Impact reports are generated with simulated labels.

### Definition of Done
- Risk graph is fully populated and queryable.
- Propagation engine works correctly.
- All risk analysis features are available.

---

## Phase 6: Disruption Simulation

### Objectives
- Implement scenario definition and management.
- Build Monte Carlo simulation engine.
- Create sensitivity analysis tools.
- Support combined disruptions.

### Deliverables
- Scenario definition and management API
- Monte Carlo simulation engine
- Sensitivity analysis engine
- Combined disruption modeling
- Simulation result aggregation and reporting
- Reproducibility framework (seed management)

### Dependencies
- Phase 5 complete.
- Risk graph and scenario infrastructure available.

### Risks
- Simulation performance may need optimization for large scenarios.
- Probability distributions may need calibration.

### Verification Checklist
- Scenarios can be defined and stored.
- Monte Carlo simulations produce statistically valid results.
- Sensitivity analysis identifies key parameters.
- Combined disruptions are modeled correctly.
- Results are reproducible with fixed seeds.
- All simulation outputs are labeled as simulated.

### Definition of Done
- Simulation engine is functional.
- All scenario types are supported.
- Results are reproducible and properly labeled.

---

## Phase 7: Decision Replay Lab

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
- Phase 6 complete.
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

---

## Phase 8: Optimization Engine

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
- Phase 7 complete.
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

---

## Phase 9: AI Decision Copilot

### Objectives
- Implement LLM integration with controlled tool calling.
- Build intent classification and tool routing.
- Implement guardrails and audit logging.
- Add human approval workflow for consequential actions.

### Deliverables
- LLM provider abstraction layer
- Intent classification system
- Tool registry and execution engine
- Guardrail enforcement
- Audit logging for all AI interactions
- Human approval workflow
- Rate limiting
- Evidence-backed response generation

### Dependencies
- Phase 8 complete.
- All analytical modules are functional.
- LLM API key configured.

### Risks
- LLM may hallucinate; guardrails must be robust.
- Tool execution errors must be handled gracefully.
- Rate limiting may affect usability.

### Verification Checklist
- LLM integration works with replaceable provider.
- Intent classification correctly routes to tools.
- Guardrails prevent unauthorized actions.
- All AI responses include evidence and confidence.
- Audit logs capture all interactions.
- Human approval workflow is functional.
- Simulated data is labeled correctly.

### Definition of Done
- AI Decision Copilot is fully functional.
- All guardrails are enforced.
- Audit and approval workflows are working.

---

## Phase 10: Frontend Dashboard

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
- Phase 9 complete.
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

---

## Phase 11: Governance, Testing, Deployment, and Portfolio Packaging

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
- Phase 10 complete.
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