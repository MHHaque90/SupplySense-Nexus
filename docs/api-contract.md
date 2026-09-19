# API Contract: SupplySense Nexus

## Overview

The API follows REST conventions with JSON request/response bodies. All endpoints are versioned under `/api/v1`. Authentication is via API key (future: JWT). Health endpoints are publicly accessible.

All responses follow a consistent envelope format:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "timestamp": "2026-09-19T12:00:00Z",
    "data_source_label": "simulated"
  }
}
```

## General Rules

- All API responses include a `data_source_label` in the meta field.
- Simulated/estimated data is always labeled with `data_source_label: "simulated"`.
- All mutating endpoints require authentication.
- All endpoints support consistent error responses.
- Pagination uses `limit` and `offset` query parameters.
- Timestamps use ISO 8601 format.

## Health Endpoints

### GET /api/v1/health

**Purpose**: Health check. Returns service status.
**Auth**: None
**Response**: `HealthResponse` (status, app_name, version, phase)

### GET /api/v1/health/live

**Purpose**: Liveness probe.
**Auth**: None

### GET /api/v1/health/ready

**Purpose**: Readiness probe.
**Auth**: None

## Data Ingestion Endpoints

### POST /api/v1/data/ingest

**Purpose**: Ingest data from files or external sources.
**Auth**: Required (manager or above)
**Request**: `DataIngestionRequest` { source_type, file_path, data_source_label }
**Response**: `IngestionResult` { batch_id, record_count, status }
**Errors**: Invalid file format, unsupported source type, authentication failure

### POST /api/v1/data/quality-check

**Purpose**: Run data quality validation on a dataset.
**Auth**: Required (analyst or above)
**Request**: `QualityCheckRequest` { table_name, checks[] }
**Response**: `QualityCheckResult` { passed, failures[], summary }
**Read-only**: Yes

### GET /api/v1/data/quality-reports

**Purpose**: List data quality reports.
**Auth**: Required (analyst or above)
**Response**: List of quality reports
**Read-only**: Yes

## Product Endpoints

### GET /api/v1/products

**Purpose**: List products with optional filtering.
**Auth**: Required
**Query params**: `product_id`, `category_id`, `data_source_label`, `limit`, `offset`
**Response**: Paginated list of products
**Read-only**: Yes

### GET /api/v1/products/{id}

**Purpose**: Get product details.
**Auth**: Required
**Response**: Product detail
**Read-only**: Yes

### GET /api/v1/product-categories

**Purpose**: List product categories.
**Auth**: Required
**Response**: List of categories
**Read-only**: Yes

## Inventory Endpoints

### GET /api/v1/inventory/position

**Purpose**: Get current inventory position across warehouses.
**Auth**: Required
**Query params**: `warehouse_id`, `product_id`, `date`
**Response**: `InventoryPosition` { available, reserved, in_transit, days_of_supply }
**Read-only**: Yes

### GET /api/v1/inventory/safety-stock

**Purpose**: Calculate safety stock levels.
**Auth**: Required
**Response**: `SafetyStockResult` { product_id, warehouse_id, safety_stock, reorder_point }
**Read-only**: Yes

### GET /api/v1/inventory/stockout-risk

**Purpose**: Estimate stockout risk for products.
**Auth**: Required
**Response**: `StockoutRiskResult` { product_id, warehouse_id, probability, estimated_shortfall }
**Read-only**: Yes

### GET /api/v1/inventory/transactions

**Purpose**: List inventory transactions.
**Auth**: Required
**Query params**: `warehouse_id`, `product_id`, `date_from`, `date_to`, `limit`, `offset`
**Response**: Paginated transaction list
**Read-only**: Yes

### GET /api/v1/inventory/turnover

**Purpose**: Calculate inventory turnover metrics.
**Auth**: Required
**Response**: `TurnoverResult` { product_id, turnover_rate, days_inventory, working_capital_exposure }
**Read-only**: Yes

## Supplier Endpoints

### GET /api/v1/suppliers

**Purpose**: List suppliers.
**Auth**: Required
**Query params**: `name`, `country`, `data_source_label`, `limit`, `offset`
**Response**: Paginated supplier list
**Read-only**: Yes

### GET /api/v1/suppliers/{id}/scorecard

**Purpose**: Get supplier scorecard.
**Auth**: Required
**Response**: `SupplierScorecard` { on_time_delivery, quality_score, cost_score, lead_time_reliability }
**Read-only**: Yes

### GET /api/v1/suppliers/{id}/products

**Purpose**: List products supplied by a supplier.
**Auth**: Required
**Response**: List of supplier-product mappings
**Read-only**: Yes

### GET /api/v1/suppliers/alternatives/{product_id}

**Purpose**: Find alternative suppliers for a product.
**Auth**: Required
**Response**: List of alternative suppliers with comparison metrics
**Read-only**: Yes

### GET /api/v1/suppliers/concentration

**Purpose**: Analyze supplier concentration risk.
**Auth**: Required
**Response**: `ConcentrationResult` { hhi, top_supplier_share, single_source_count }
**Read-only**: Yes

## Forecast Endpoints

### GET /api/v1/forecasts/generate

**Purpose**: Trigger a forecast generation run.
**Auth**: Required (analyst or above)
**Request**: `ForecastRequest` { product_id, horizon_days, model_version_id }
**Response**: `ForecastResult` { forecast_id, status }
**Mutating**: Yes (creates forecast run)

### GET /api/v1/forecasts/{id}

**Purpose**: Get forecast results.
**Auth**: Required
**Response**: `ForecastDetail` { point_estimate, lower_bound, upper_bound, confidence_level }
**Read-only**: Yes

### GET /api/v1/forecasts/compare

**Purpose**: Compare multiple forecast models.
**Auth**: Required (analyst or above)
**Request**: `ForecastComparisonRequest` { product_id, model_types[], date_range }
**Response**: `ComparisonResult` { metrics_by_model, best_model }
**Read-only**: Yes

### GET /api/v1/forecasts/drift

**Purpose**: Check for model drift.
**Auth**: Required
**Response**: `DriftReport` { model_id, drift_detected, metrics }
**Read-only**: Yes

## Risk Endpoints

### GET /api/v1/risk/dependency-map

**Purpose**: Get supply-chain dependency graph.
**Auth**: Required
**Response**: `DependencyMap` { nodes[], edges[], critical_components[] }
**Read-only**: Yes

### GET /api/v1/risk/single-point-of-failure

**Purpose**: Identify single points of failure.
**Auth**: Required
**Response**: `SPOFResult` { components[], impact_analysis[] }
**Read-only**: Yes

### GET /api/v1/risk/propagation/{entity_id}

**Purpose**: Simulate disruption propagation from an entity.
**Auth**: Required
**Response**: `PropagationResult` { affected_entities[], severity_levels[] }
**Read-only**: Yes

## Scenario Endpoints

### POST /api/v1/scenarios

**Purpose**: Create a new scenario.
**Auth**: Required (analyst or above)
**Request**: `ScenarioRequest` { name, description, scenario_type, base_assumptions }
**Response**: `ScenarioResponse` { scenario_id, status }
**Mutating**: Yes

### GET /api/v1/scenarios/{id}

**Purpose**: Get scenario details and results.
**Auth**: Required
**Response**: `ScenarioDetail` { events[], results[], assumptions }
**Read-only**: Yes

### POST /api/v1/scenarios/{id}/simulate

**Purpose**: Run Monte Carlo simulation for a scenario.
**Auth**: Required (analyst or above)
**Request**: `SimulationRequest` { num_iterations, seed }
**Response**: `SimulationResult` { iteration_count, expected_values[], confidence_intervals[] }
**Mutating**: Yes

### GET /api/v1/scenarios/{id}/sensitivity

**Purpose**: Run sensitivity analysis.
**Auth**: Required
**Response**: `SensitivityResult` { parameters[], ranges[], results[] }
**Read-only**: Yes

## Decision Replay Endpoints

### POST /api/v1/decision-options

**Purpose**: Generate decision options for a scenario.
**Auth**: Required (analyst or above)
**Request**: `DecisionOptionsRequest` { scenario_id, option_types[] }
**Response**: `DecisionOptionsResponse` { options[] }
**Mutating**: Yes

### GET /api/v1/decision-comparisons/{scenario_id}

**Purpose**: Compare all decision options for a scenario.
**Auth**: Required
**Response**: `DecisionComparison` { baseline, alternatives[], ranking[], confidence }
**Read-only**: Yes

### POST /api/v1/decision-comparisons/{scenario_id}/rank

**Purpose**: Rank decision options and generate recommendation.
**Auth**: Required (manager or above)
**Request**: `RankingRequest` { weights for cost, service, risk }
**Response**: `RankingResponse` { recommended_option, rationale, confidence }
**Mutating**: Yes

### GET /api/v1/decision-history

**Purpose**: List past decision comparisons.
**Auth**: Required
**Response**: Paginated decision history
**Read-only**: Yes

## Optimization Endpoints

### POST /api/v1/optimization/run

**Purpose**: Run an optimization model.
**Auth**: Required (analyst or above)
**Request**: `OptimizationRequest` { scenario_id, objective, constraints }
**Response**: `OptimizationResponse` { run_id, status, solution }
**Mutating**: Yes

### GET /api/v1/optimization/{run_id}

**Purpose**: Get optimization results.
**Auth**: Required
**Response**: `OptimizationResult` { status, objective_value, solution, violations }
**Read-only**: Yes

### GET /api/v1/optimization/pareto-front

**Purpose**: Get Pareto-optimal solutions for multi-objective optimization.
**Auth**: Required
**Response**: `ParetoFront` { solutions[], tradeoff_curves[] }
**Read-only**: Yes

## AI Assistant Endpoints

### POST /api/v1/ai/chat

**Purpose**: Send a natural-language question to the AI copilot.
**Auth**: Required
**Request**: `AIChatRequest` { message, conversation_id? }
**Response**: `AIChatResponse` { response, confidence, evidence[], limitations[], approved }
**Mutating**: Yes (logs to audit)

### GET /api/v1/ai/tools

**Purpose**: List available AI tools.
**Auth**: Required
**Response**: List of tools with descriptions and schemas
**Read-only**: Yes

### POST /api/v1/ai/approval

**Purpose**: Submit consequential decision for human approval.
**Auth**: Required (manager or above)
**Request**: `ApprovalRequest` { decision_id, description, impact_summary }
**Response**: `ApprovalResponse` { approval_id, status }
**Mutating**: Yes

## Governance Endpoints

### GET /api/v1/governance/models

**Purpose**: List registered model versions.
**Auth**: Required (admin or above)
**Response**: List of model versions
**Read-only**: Yes

### POST /api/v1/governance/models

**Purpose**: Register a new model version.
**Auth**: Required (admin)
**Request**: `ModelRegistrationRequest` { model_name, model_type, metrics, file_path }
**Response**: `ModelRegistrationResponse` { model_version_id }
**Mutating**: Yes

### GET /api/v1/governance/audit-logs

**Purpose**: View audit log entries.
**Auth**: Required (admin)
**Query params**: `user_id`, `action`, `date_from`, `date_to`, `limit`, `offset`
**Response**: Paginated audit log entries
**Read-only**: Yes

### GET /api/v1/governance/data-quality

**Purpose**: Get data quality reports.
**Auth**: Required (admin)
**Response**: `DataQualityReport` { checks[], summary, recommendations }
**Read-only**: Yes

## Error Cases

All errors follow this format:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}
  },
  "meta": { "timestamp": "..." }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| VALIDATION_ERROR | 422 | Invalid request parameters |
| AUTHENTICATION_ERROR | 401 | Missing or invalid credentials |
| PERMISSION_DENIED | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource conflict |
| INTERNAL_ERROR | 500 | Internal server error |
| SERVICE_UNAVAILABLE | 503 | Service temporarily unavailable |
| AI_UNAVAILABLE | 503 | AI service unavailable |

## Safety Rules

- The AI assistant endpoint **never** executes arbitrary SQL or Python.
- Procurement actions require explicit human approval.
- All AI responses include confidence levels and limitations.
- All data returned by AI tools is labeled with `data_source_label`.
- The AI assistant has **read-only** access to analytical data.
