# Testing Strategy: SupplySense Nexus

## Overview

The testing strategy ensures reliability, correctness, and reproducibility across all modules. Testing covers unit, integration, API, database, data-quality, forecasting, optimization, simulation, AI, security, regression, and performance domains.

## Unit Testing

### Scope
- Individual functions and methods in isolation.
- Pydantic schema validation.
- Data validation logic.
- Helper utilities.

### Framework
- **pytest** with **pytest-cov** for coverage reporting.
- **mypy** for static type checking.

### Coverage Target
- Minimum 80% line coverage for core modules.
- 100% coverage for critical paths (data validation, security).

### Example Tests
- Product schema validation: Valid and invalid product data.
- Data validation rules: Range checks, format checks, referential checks.
- Configuration loading: Environment variable parsing and defaults.
- Utility functions: Date formatting, string manipulation, etc.

## Integration Testing

### Scope
- Database CRUD operations.
- API endpoint integration.
- Module-to-module communication.
- External service integration (LLM, data sources).

### Framework
- **pytest** with **httpx** for API testing.
- **TestClient** from FastAPI for endpoint testing.
- **SQLAlchemy async session** for database testing.

### Test Data
- Use isolated test databases.
- Each test creates its own data and cleans up afterward.
- Synthetic test data only.

## API Testing

### Scope
- All API endpoints (health, data, forecast, supplier, scenario, decision, optimization, AI, governance).
- Request validation, response shape, error handling.
- Authentication and authorization.

### Tests Per Endpoint
1. **Success case**: Valid request returns 200 with correct response shape.
2. **Validation error**: Invalid request returns 422 with error details.
3. **Authentication**: Missing/invalid credentials return 401.
4. **Authorization**: Insufficient permissions return 403.
5. **Not found**: Non-existent resource returns 404.
6. **Rate limiting**: Excessive requests return 429 (when implemented).

### Response Shape Validation
- All responses match Pydantic schemas.
- `data_source_label` is present in all responses.
- Error responses have consistent structure.

## Database Testing

### Scope
- Schema integrity (tables, columns, constraints, indexes).
- Foreign key relationships.
- Data insertion, retrieval, update, deletion.
- Transaction handling and rollback.

### Tests
- Table creation and schema validation.
- Referential integrity enforcement.
- Constraint violations are properly rejected.
- Query performance within acceptable thresholds.
- Migration scripts (Alembic) execute correctly.

## Data-Quality Testing

### Scope
- Completeness checks (null values, missing fields).
- Range checks (valid values, boundaries).
- Uniqueness checks (duplicate detection).
- Referential integrity checks (orphaned foreign keys).
- Temporal consistency checks (ordering, overlaps).

### Tests
- Run data-quality checks on synthetic datasets with known issues.
- Verify that checks correctly identify and report problems.
- Validate that imputation logic works correctly.
- Confirm that data-quality reports are generated accurately.

## Forecast Backtesting

### Scope
- Walk-forward validation of forecasting models.
- Evaluation metric computation (MAE, RMSE, MAPE, WMAPE).
- Prediction interval calibration.
- Model selection logic.

### Tests
- Verify that walk-forward validation produces consistent results.
- Check that forecast intervals have target coverage (e.g., 95% intervals cover 95% of actuals).
- Validate that model selection picks the best performer on validation data.
- Confirm that backtesting results are reproducible with fixed seeds.

**Note**: Metrics are computed during testing but are not pre-claimed or fabricated.

## Optimization Feasibility Testing

### Scope
- Constraint satisfaction verification.
- Solution feasibility checks.
- Infeasible problem detection.
- Performance of solver under various constraints.

### Tests
- Verify that feasible problems return feasible solutions.
- Verify that infeasible problems are correctly identified.
- Check that constraint violations are reported.
- Validate that optimization results match manual calculations for simple cases.
- Confirm that multi-objective optimization produces Pareto-optimal solutions.

## Simulation Reproducibility Testing

### Scope
- Monte Carlo simulation reproducibility.
- Random seed consistency.
- Statistical properties of simulation outputs.

### Tests
- Run the same simulation twice with the same seed; verify identical results.
- Run the same simulation with different seeds; verify different results.
- Verify that sample statistics converge to expected values with sufficient iterations.
- Confirm that scenario parameters are correctly reflected in results.

## AI Tool-Contract Testing

### Scope
- Tool input/output schema validation.
- Tool execution correctness.
- Guardrail compliance.
- Intent classification accuracy.

### Tests
- Verify each tool accepts valid inputs and rejects invalid inputs.
- Verify tool outputs match expected schemas.
- Test guardrail violations: Attempt SQL execution, arbitrary Python execution, procurement modification.
- Verify that AI responses include confidence levels and limitations.
- Test that simulated data is labeled correctly.
- Verify that human approval is required for mutating actions.

## Security Testing

### Scope
- SQL injection prevention.
- Authentication bypass attempts.
- Authorization escalation attempts.
- Input validation and sanitization.
- API key validation.

### Tests
- Attempt SQL injection through all input fields; verify rejection.
- Attempt to access another organization's data; verify rejection.
- Attempt to access protected endpoints without authentication; verify 401.
- Attempt to access admin endpoints with analyst role; verify 403.
- Verify that all inputs are properly sanitized.
- Check for exposed secrets in code and configuration.

## Regression Testing

### Scope
- Ensure new changes don't break existing functionality.
- Run full test suite on every code change.
- Track test coverage over time.

### Strategy
- Automated test suite runs on every pull request.
- Critical path tests run on every commit.
- Full suite runs nightly or on release candidates.
- Any failing test blocks merging.

## Frontend Testing

### Scope
- HTML structure and rendering.
- CSS responsive behavior.
- JavaScript interaction logic.
- Chart.js visualizations.

### Tests
- Page loads correctly and displays all sections.
- Responsive layout works on different screen sizes.
- JavaScript functions execute without errors.
- Data labels are displayed correctly on charts.
- Accessibility: All interactive elements are keyboard-navigable.

### Framework
- Playwright for end-to-end browser testing.
- Manual visual inspection for responsive design.

## Performance Testing

### Scope
- API response times.
- Database query performance.
- Forecast generation time.
- Simulation execution time.
- Concurrency handling.

### Tests
- API endpoints respond within 500ms (95th percentile) for standard queries.
- Database queries complete within acceptable time for dataset sizes.
- Forecast generation completes within 60 seconds for 10K demand observations.
- Monte Carlo simulation with 10K iterations completes within 120 seconds.
- System handles concurrent users without degradation.

### Tools
- **pytest-benchmark** for benchmarking critical functions.
- **Locust** or **k6** for load testing (when implemented).

## Acceptance Criteria

### Phase 0 Acceptance
1. All 10 documentation files are created and complete.
2. AGENTS.md is created with all required sections.
3. Project structure is correct.
4. Health endpoint passes tests.
5. FastAPI application imports without errors.
6. Configuration files are valid.
7. README is complete and accurate.

### Phase 1 Acceptance
1. PostgreSQL schema is implemented and migrations run.
2. Data ingestion endpoints work correctly.
3. Data-quality checks pass for synthetic data.
4. All database tests pass.

### Phase 2 Acceptance
1. Baseline forecasting models are implemented and tested.
2. Forecast backtesting produces valid results.
3. Data-quality reports are generated.

### Phase 3 Acceptance
1. Forecasting models are trained and evaluated.
2. Prediction intervals are computed.
3. Inventory intelligence features work correctly.

### Phase 4+ Acceptance
- Each phase has its own acceptance criteria defined in the roadmap.

## Test Data Policy

- All test data is synthetic or generated.
- No real company data is used in testing.
- Test databases are isolated from production databases.
- Test data is cleaned up after each test run.

## Test Reporting

- Test results are reported in CI/CD pipeline output.
- Coverage reports are generated for each test run.
- Failed tests are categorized and prioritized.
- Test results are archived for trend analysis.