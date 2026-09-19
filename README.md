# SupplySense Nexus

AI-Powered Supply Chain Resilience and Decision Intelligence Platform

## Overview

SupplySense Nexus helps supply-chain teams understand demand, inventory, suppliers, procurement, disruptions, and operational trade-offs. Its central differentiator is **disruption-aware procurement decision intelligence**.

## Core Capability

The platform answers questions such as:

- What happens if a supplier is delayed?
- Which products or warehouses will be affected?
- Should the company wait, expedite, reallocate inventory, or use an alternative supplier?
- What is the expected cost of each option?
- How will each option affect service level and stockout risk?
- Which decision provides the best balance between cost, service, and risk?
- How confident is the recommendation?
- Which data, assumptions, and models produced the recommendation?

## Technology Stack

- **Backend**: Python 3.14, FastAPI, Pydantic, SQLAlchemy, Alembic
- **Database**: PostgreSQL 17
- **Analytics**: Pandas, NumPy, Scikit-learn, Statsmodels
- **Optimization**: OR-Tools
- **Frontend**: HTML, CSS, Vanilla JavaScript, Chart.js
- **Testing**: pytest, Ruff, mypy
- **Deployment**: Docker, Docker Compose (when available)

## Project Structure

```
backend/          # FastAPI application
frontend/         # HTML/CSS/JS dashboard
docs/             # Architecture and design documentation
backend/app/      # Core application code
backend/app/tests/# Test suite
```

## Getting Started

See [docs/roadmap.md](docs/roadmap.md) for the full development plan and setup instructions.

## Status

Phase 0: Repository Audit, Product Definition, System Architecture, and Development Foundation.

## Data Policy

All data is clearly labeled as public, synthetic, user-provided, derived, or simulated. Synthetic and simulated outputs are always explicitly identified.

## License

Portfolio project. No real company data is used without permission.
