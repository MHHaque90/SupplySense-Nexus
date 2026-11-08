# SupplySense Nexus

AI-Powered Supply Chain Resilience and Decision Intelligence Platform

## Overview

SupplySense Nexus helps supply-chain teams understand demand, inventory, suppliers, procurement, disruptions, and operational trade-offs. Its central differentiator is **disruption-aware procurement decision intelligence**.

## Core Capability

The platform answers questions such as:

- What happens if a supplier is delayed?
- Which products or warehouses will be affected?
- What are the trade-offs between waiting, expediting, reallocating inventory, or using an alternative supplier?
- What is the expected cost of each option?
- How will each option affect service level and stockout risk?
- How do the options compare across cost, service, and risk?
- How confident are these figures?
- Which data, assumptions, and models produced these figures?

The platform presents factual differences, trade-off quantities, assumptions, and uncertainties — it never ranks options or issues recommendations; decisions stay with the human.

## Technology Stack

- **Backend**: Python 3.12+ (tested up to 3.14), FastAPI, Pydantic, SQLAlchemy, Alembic
- **Database**: PostgreSQL 17
- **Analytics**: Pandas, NumPy, Scikit-learn, Statsmodels
- **Optimization**: SciPy / HiGHS (deterministic MILP)
- **Frontend**: React 19, TypeScript, Vite
- **Testing**: pytest, pytest-cov, Ruff, Vitest
- **Deployment**: Docker, Docker Compose, GitHub Actions CI

## Project Structure

```
backend/          # FastAPI application
frontend/         # React 19 / TypeScript / Vite dashboard
docs/             # Architecture and design documentation
backend/app/      # Core application code
backend/app/tests/# Test suite (854 tests, 96% line coverage)
```

## Getting Started

See [docs/roadmap.md](docs/roadmap.md) for the full development plan and setup instructions.

## Status

Phase 0: Repository Audit, Product Definition, System Architecture, and Development Foundation — complete.
Phase 1: Data Foundation and PostgreSQL Schema (31 tables, models, migrations, 16 tests) — complete.
Phase 2: Synthetic ERP data foundation — complete. See "Synthetic Data" below.
Phase 3: Analytics foundation (datasets, features, baselines, validation, KPIs, reports, 67 tests) — complete. See "Analytics" and [docs/analytics-foundation.md](docs/analytics-foundation.md).
Phase 4: Demand forecasting — complete. See "Forecasting" and [docs/demand-forecasting.md](docs/demand-forecasting.md).
Phase 5: Inventory intelligence — complete. See "Inventory Intelligence" and [docs/inventory-intelligence.md](docs/inventory-intelligence.md).
Phase 6: Supplier & procurement intelligence — complete. See "Supplier & Procurement Intelligence" and [docs/supplier-procurement-intelligence.md](docs/supplier-procurement-intelligence.md).
Phase 7: Supply-chain risk intelligence — complete. See "Risk Intelligence" and [docs/supply-chain-risk-intelligence.md](docs/supply-chain-risk-intelligence.md).
Phase 8: Disruption simulation — complete. See "Disruption Simulation" and [docs/disruption-simulation.md](docs/disruption-simulation.md).
Phase 9: Decision Replay Lab (factual decision comparison, 120 tests) — complete. See [docs/decision-replay-lab.md](docs/decision-replay-lab.md).
Phase 10: Optimization Engine (deterministic MILP, 130 tests) — complete. See "Optimization Engine" and [docs/optimization-engine.md](docs/optimization-engine.md).
Phase 11: AI Decision Copilot (opaque API-key auth, 3 endpoints, 103 tests) — complete. See "AI Decision Copilot" and [docs/ai-decision-copilot.md](docs/ai-decision-copilot.md).
Phase 12A: Backend API Foundation (11 API route domains, fail-closed auth) — complete. See [docs/api-contract.md](docs/api-contract.md).
Phase 12B: Modern React Dashboard (React 19, TypeScript, Vite SPA) — complete.
Phase 13: CI/CD, Containerization & Model Governance Foundation (GitHub Actions, Docker, drift monitoring) — complete.
Phase 14: Enterprise Dark Visual Refinement (Slate-Navy & Restrained Cobalt design) — complete.
Phase 15: Local Development Authentication & Security Hardening (dev key issuance CLI, fail-closed production controls) — complete.
Phase 16: Functional Acceptance & Decision Intelligence Validation (11 routes validated, 854 backend tests passed, 96% coverage, 42 frontend tests passed) — complete and accepted.
Phase 17: Pre-Git Security & Open-Source Release Preparation (readiness audit, MIT license, repository packaging) — complete (local pre-release state; not yet published to GitHub).

## Synthetic Data

**This dataset is synthetic and is generated solely for demonstration, testing, analytics development, and portfolio purposes.** It does not represent any real company, supplier, product, or market behavior.

Generate the default deterministic dataset (seed 42, 1 organization, 24 products, 8 suppliers, 3 warehouses, 365 days of history):

```bash
python scripts/generate_synthetic_data.py generate --seed 42
```

Other commands: `validate`, `report`, `reset`, `sample`. Run with `--help` on any subcommand for options (`--organization-count`, `--product-count`, `--supplier-count`, `--warehouse-count`, `--history-days`, `--reset`).

Every operational record carries `data_source_label = "synthetic"`; disruption records carry `"simulated"`. Generation, ingestion, validation, and reporting are documented in [docs/data-strategy.md](docs/data-strategy.md). Sample CSVs live in `data/sample/`; the machine- and human-readable dictionary lives in `data/dictionaries/`.

## Analytics

Phase 3 provides the analytical foundation (production forecasting is Phase 4). See [docs/analytics-foundation.md](docs/analytics-foundation.md).

```bash
python scripts/analyze_supply_chain.py demand --aggregation week
python scripts/analyze_supply_chain.py inventory
python scripts/analyze_supply_chain.py procurement
python scripts/analyze_supply_chain.py forecast --forecast-horizon 28
python scripts/analyze_supply_chain.py report --output-json report.json --output-markdown report.md
```

All analytics run on SYNTHETIC data; every report carries the synthetic-data disclaimer.

## Forecasting

Phase 4 forecasting is documented in [docs/demand-forecasting.md](docs/demand-forecasting.md).

```bash
python scripts/analyze_supply_chain.py forecast \
  --product-id <uuid> --warehouse-id <uuid> --forecast-horizon 28 --metric wape

python scripts/analyze_supply_chain.py forecast-report \
  --forecast-horizon 14 --max-series 20 --output-json report.json

# Persist selected forecasts to model_versions / forecasts (no migration)
python scripts/analyze_supply_chain.py forecast --product-id <uuid> --warehouse-id <uuid> --persist
```

All forecasts are of synthetic generated demand; every output carries `SYNTHETIC DATA — NOT REAL BUSINESS PERFORMANCE`.

## Inventory Intelligence

Phase 5 intelligence is documented in [docs/inventory-intelligence.md](docs/inventory-intelligence.md). Signals only — no optimization, no safety-stock calculation, no order quantities.

```bash
python scripts/analyze_supply_chain.py inventory-intelligence \
  --product-id <uuid> --warehouse-id <uuid> --forecast-horizon 28

python scripts/analyze_supply_chain.py inventory-intelligence \
  --health AT_RISK --output-json inventory.json --output-markdown inventory.md
```

## Supplier & Procurement Intelligence

Phase 6 intelligence is documented in [docs/supplier-procurement-intelligence.md](docs/supplier-procurement-intelligence.md). Descriptive only — no supplier ranking, no recommendations, no optimization.

```bash
python scripts/analyze_supply_chain.py procurement-intelligence \
  --supplier-id <uuid> --forecast-horizon 28 \
  --include-exposure --include-concentration \
  --output-json procurement.json --output-markdown procurement.md
```

## Risk Intelligence

Phase 7 intelligence is documented in [docs/supply-chain-risk-intelligence.md](docs/supply-chain-risk-intelligence.md). Risk identification and explanation only — no optimization, simulation, Replay, or Copilot.

```bash
python scripts/analyze_supply_chain.py risk-intelligence \
  --forecast-horizon 28 --severity HIGH \
  --output-json risk.json --output-markdown risk.md
```

## Disruption Simulation

Phase 8 simulation is documented in [docs/disruption-simulation.md](docs/disruption-simulation.md). Baseline-vs-scenario analysis only — no decision comparison, optimization, or prescriptions.

```bash
python scripts/analyze_supply_chain.py disruption-simulation \
  --scenario SUPPLIER_OUTAGE --supplier-id <uuid> --horizon-days 28 \
  --output-json sim.json --output-markdown sim.md
```

All scenarios are hypothetical and labeled simulated; never predictions or historical facts.

## Optimization Engine

Phase 10 optimization is documented in [docs/optimization-engine.md](docs/optimization-engine.md). Constraint-based procurement planning over the disruption horizon: four explicit objectives, MILP solver (HiGHS via SciPy), feasibility diagnostics, and a factual comparison against the Phase 9 baseline. Outputs are simulated planning results — never prescriptions, rankings, or "best" answers.

```bash
python scripts/analyze_supply_chain.py optimization \
  --start-date 2026-06-01 --end-date 2026-06-30 \
  --scenario SUPPLY_REDUCTION --supplier-id <uuid> \
  --objective minimize_total_cost --horizon-days 28 \
  --output-json optimization.json --output-markdown optimization.md
```

## AI Decision Copilot

Phase 11 copilot is documented in [docs/ai-decision-copilot.md](docs/ai-decision-copilot.md) (design in [docs/ai-assistant-design.md](docs/ai-assistant-design.md)). Natural-language questions over the platform's evidence: opaque Bearer API-key auth, 8-intent classifier, 13 controlled tools (7 read-only, 3 compute, 3 approval declarations), guardrails, per-role rate limiting, PostgreSQL conversation history. It never executes SQL/Python, never mutates data, and never ranks or recommends — approvals record a human decision and never execute.

```bash
curl -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Authorization: Bearer ssk_..." -H "Content-Type: application/json" \
  -d '{"message": "Show inventory health for warehouse 3."}'

curl -H "Authorization: Bearer ssk_..." http://localhost:8000/api/v1/ai/tools
```

LLM provider defaults to the deterministic MockProvider (`ENABLE_AI_ASSISTANT=false`, no key needed); set `ENABLE_AI_ASSISTANT=true` with `AI_PROVIDER=openai` and `OPENAI_API_KEY` to use an OpenAI-compatible endpoint (httpx only).

## Data Policy

All data is clearly labeled as public, synthetic, user-provided, derived, or simulated. Synthetic and simulated outputs are always explicitly identified.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
All operational ERP data is synthetic; no real company data is used.
