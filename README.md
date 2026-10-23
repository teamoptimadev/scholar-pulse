# ScholarPulse — Academic Performance Monitoring & Institutional Analytics

**Team:** SMK

**Members:**
- Srivatsa Kamble — 20231CSE0257
- Kishore S V — 20231CSE0260
- Mohan A — 20231CSE0273

**Guide:** Nayeem Akhtar Sholapur

---

## Project Overview

A software-only academic performance monitoring and institutional analytics platform. The system enables universities and institutions to track student performance, generate analytics, predict outcomes, and identify at-risk students using machine learning — all within a secure multi-tenant architecture.

## Problem Statement

Educational institutions struggle to monitor student performance at scale, identify at-risk students early, and provide data-driven insights to administrators, faculty, students, and parents. Manual tracking and fragmented systems make it difficult to deliver timely interventions and institutional analytics.

## Objectives

- Provide a unified platform for academic performance monitoring across an institution
- Enable ML-powered predictions for performance, pass/fail outcomes, and at-risk detection
- Deliver role-specific dashboards for admins, students, faculty, and parents
- Ensure complete data isolation between institutions (multi-tenant)
- Support institutional, department, and subject-level analytics

## Main Features

| Portal | Key Capabilities |
|--------|------------------|
| **Institution Admin** | Analytics dashboard, department/subject analytics, student management, predictions, at-risk detection, reports |
| **Student** | Academic profile, performance, predictions, improvement areas, goal setting, reports |
| **Faculty** | Assigned students, performance tracking, predictions, at-risk students, reports |
| **Parent** | Child performance, predictions, improvement areas, reports |

## Architecture

```
Next.js Client (Bun)
        ↓
FastAPI Backend (uv)
        ↓
PostgreSQL
        ↓
ML Prediction Layer (versioned model artifacts)
```

Each institution operates as an independent tenant with backend-enforced data isolation.

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Client** | Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, react-hook-form, zod, Bun |
| **Backend** | FastAPI, Python, SQLAlchemy, Alembic, argon2-cffi, PyJWT, slowapi, WeasyPrint, uv |
| **Database** | PostgreSQL (Alembic migrations) |
| **ML** | Pandas, NumPy, Scikit-learn, joblib, Jupyter (uv) |
| **CI** | GitHub Actions (pytest, ruff, eslint, build) |
| **Infrastructure** | Docker Compose (PostgreSQL), Sentry (optional) |

## Repository Structure

```
scholar-pulse/
├── client/          # Next.js frontend (Bun)
├── backend/         # FastAPI API server (uv)
├── ml/              # ML development & training (uv)
├── docs/            # Project documentation
├── docker-compose.yml
├── .env.example
└── README.md
```

## ML Pipeline

```
university_data/*.csv → Training → .pkl / .json artifacts → Python inference → FastAPI
```

Three components trained on the synthetic CBCS university dataset:
1. **Performance Prediction** — end-term marks from 0-100 via HistGradientBoostingRegressor
2. **Pass/Fail Prediction** — PASS/FAIL classification with probabilities via HistGradientBoostingClassifier, tuned for FAIL recall
3. **At-Risk Detection** — versioned rule-based weighted risk engine (not ML)

Current held-out results:

| Component | Metrics |
|-----------|---------|
| Model 1 — end-term marks | MAE 5.6549 · RMSE 7.0895 · R² 0.7574 |
| Model 2 — pass/fail | FAIL recall 0.9519 · FAIL precision 0.1606 · ROC-AUC 0.9912 |
| Model 3 — risk engine | Accuracy 74.85% · macro F1 70.78% |

Model 2's test-set FAIL rate is 0.81%, so its precision/recall trade-off should be considered alongside its always-PASS accuracy of 0.9919. These synthetic-dataset results are not guarantees of institutional performance. See [ML evaluation](docs/ml-evaluation.md) for test-set details and caveats.

See [docs/ml-pipeline.md](docs/ml-pipeline.md) and [ml/README.md](ml/README.md).

Prediction and authentication endpoints under `/api/v1`:

```text
POST /predictions/performance
POST /predictions/pass-fail
POST /predictions/risk
POST /predictions/all
POST /predictions/student
POST /predictions/regenerate
POST /auth/refresh
```

## Development Phases

1. Dataset and problem definition
2. Data preprocessing and EDA
3. ML model development
4. Model evaluation and finalization
5. FastAPI backend and academic data system
6. Analytics dashboards
7. Large-scale data testing
8. Integration, testing and deployment

See [docs/development-phases.md](docs/development-phases.md) for details.

## Local Development Setup

### Prerequisites

- [Bun](https://bun.sh) (client)
- [uv](https://docs.astral.sh/uv/) (Python)
- [Docker](https://www.docker.com/) (PostgreSQL)

### 1. Start PostgreSQL

```bash
cp .env.example .env
docker compose up -d
```

### 2. Client (Next.js)

```bash
cd client
bun install
bun run dev
```

Client runs at `http://localhost:3000`.

### 3. Backend (FastAPI)

```bash
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run python scripts/seed.py --scale 100
uv run uvicorn app.main:app --reload --port 8000
```

API runs at `http://localhost:8000`. **Interactive API docs:** [Swagger UI](http://localhost:8000/docs) · [ReDoc](http://localhost:8000/redoc). Health: `GET /health`.

Default admin login: `admin@demo.com` / `admin123`. See [sample-credentials.md](sample-credentials.md) for the other seeded logins.

### 4. ML Development

```bash
cd ml
uv sync
```

## SDG Alignment

**SDG 4: Quality Education.** Early identification of at-risk students supports timely academic intervention. Role-specific academic feedback helps students, faculty, parents, and administrators act on relevant evidence.

**SDG 9: Industry, Innovation and Infrastructure.** The deployable multi-tenant analytics platform gives institutions reusable infrastructure for academic monitoring. Its prediction and reporting services turn institutional data into an operational innovation.

## Test and CI

From `/backend`, run `uv run pytest tests` and `uv run ruff check .`.

## Documentation

### Core

| Document | Description |
|----------|-------------|
| [overview.md](docs/overview.md) | Project overview and scope |
| [architecture.md](docs/architecture.md) | System architecture and technology decisions |
| [features.md](docs/features.md) | Feature list by portal |
| [development-phases.md](docs/development-phases.md) | Implementation phases |

### Database & API

| Document | Description |
|----------|-------------|
| [database.md](docs/database.md) | Database entities and seed data |
| [database-constraints.md](docs/database-constraints.md) | Indexes, uniqueness, audit fields |
| [migrations.md](docs/migrations.md) | Alembic migration strategy |
| [backend-api.md](docs/backend-api.md) | Swagger/ReDoc UI, auth, generated reference |
| [deployment.md](docs/deployment.md#backend-docs-on-github-pages) | Publish backend docs to **GitHub Pages** |
| [backend-structure.md](docs/backend-structure.md) | `backend/` layout and route modules |
| [api-reference.generated.md](docs/api-reference.generated.md) | Per-endpoint inputs/outputs (auto-generated) |
| [api.md](docs/api.md) | API categories (short index) |
| [api-conventions.md](docs/api-conventions.md) | Pagination, errors, response envelopes |

### Auth & Security

| Document | Description |
|----------|-------------|
| [authentication.md](docs/authentication.md) | Authentication flows |
| [security.md](docs/security.md) | argon2, PyJWT, rate limiting |
| [authorization.md](docs/authorization.md) | Role-permission matrix |
| [onboarding.md](docs/onboarding.md) | Admin signup and onboarding |
| [multi-tenancy.md](docs/multi-tenancy.md) | Multi-tenant isolation |
| [user-roles.md](docs/user-roles.md) | User roles and access |
| [user-management.md](docs/user-management.md) | Admin user management |

### ML

| Document | Description |
|----------|-------------|
| [dataset.md](docs/dataset.md) | Dataset strategy |
| [ml-pipeline.md](docs/ml-pipeline.md) | ML pipeline and models |
| [ml-evaluation.md](docs/ml-evaluation.md) | Metrics, versioning, SHAP explainability |

### Frontend & Reports

| Document | Description |
|----------|-------------|
| [frontend-stack.md](docs/frontend-stack.md) | TanStack Query, RHF, zod, auth handling |
| [reports.md](docs/reports.md) | PDF export with WeasyPrint |

### Infrastructure & CI

| Document | Description |
|----------|-------------|
| [infrastructure.md](docs/infrastructure.md) | Environments, secrets, Sentry, backup |
| [deployment.md](docs/deployment.md) | Production deployment guide |
| [e2e-testing.md](docs/e2e-testing.md) | Manual validation checklist |
| [ci.md](docs/ci.md) | GitHub Actions CI pipeline |

## Scope Exclusions

This project does **not** include: hardware/IoT, ESP32, RFID, sensors, GIS, blockchain, smart contracts, Kubernetes, Kafka, Spark, Redis, or microservices architecture.

## License

Academic project — ScholarPulse, SMK Team.
