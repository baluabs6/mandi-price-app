# Mandi Bhav — Crop Price & Mandi Transparency Platform

## Stack

| Layer | Choice |
|---|---|
| Frontend | React (React 18, react-i18next for Hindi/Telugu/English) |
| Backend | Python Flask (REST API) |
| Database | PostgreSQL |
| Cache | Redis (caches price lookups, ~15 min TTL) |
| Containerization | Docker (multi-stage builds) |
| IaC | Terraform (Azure primary, AWS for DR) |
| Cloud | Azure (Container Apps, PostgreSQL Flexible Server, Azure Cache for Redis, ACR) |
| Disaster Recovery | AWS (S3 nightly `pg_dump` backups + RDS/ECS restore runbook) |
| DevOps | GitHub Actions (CI/CD, scheduled ingestion) + an equivalent Azure DevOps pipeline |

## Architecture

### High-level overview

```
                                   ┌───────────────────────────┐
                                   │   data.gov.in / Agmarknet │
                                   │      (open govt. data)     │
                                   └──────────────┬─────────────┘
                                                  │ scheduled pull (nightly)
                                                  ▼
                     ┌────────────────────────────────────────────────┐
                     │           GitHub Actions (scheduled)             │
                     │   ingest_agmarknet.py  →  writes to Postgres     │
                     └───────────────────────┬────────────────────────┘
                                              ▼
 ┌───────────┐   HTTPS    ┌───────────────┐  reads/writes  ┌──────────────┐
 │  Browser   │──────────▶│    Frontend    │                │  PostgreSQL  │
 │ (React SPA)│◀──────────│  (nginx, SPA)  │                │   database   │
 └───────────┘            └───────┬────────┘                └──────▲───────┘
                                   │ /api/* (reverse-proxied)        │
                                   ▼                                 │
                          ┌─────────────────┐   cache reads/writes   │
                          │  Flask backend  │────────────────────────┘
                          │   (REST API)    │
                          └───┬─────────┬───┘
                              │         │
                     cache /  │         │  optional RAG call
                  rate-limit  ▼         ▼
                        ┌──────────┐ ┌───────────────────┐
                        │  Redis   │ │  Anthropic Claude  │
                        │          │ │  (POST /api/ask)   │
                        └──────────┘ └────────────────────┘
```

### Components

- **Frontend (`frontend/`)** — a React single-page app served by nginx.
  Handles language switching (Hindi/Telugu/English), filters, the price
  table, and trend charts. Talks to the backend only through `/api/*`,
  which nginx reverse-proxies to the Flask service.
- **Backend (`backend/`)** — a Flask REST API (`app.py` as the application
  factory) exposing endpoints for states/districts/crops/prices, price
  trends, anomaly detection, short-term forecasting, and the `/api/ask`
  assistant. Cross-cutting concerns (CORS, rate limiting, security
  headers, proxy trust) are configured centrally in `extensions.py` and
  `config.py`.
- **Database** — PostgreSQL, accessed via SQLAlchemy models
  (`models.py`), with schema changes managed through Flask-Migrate
  (Alembic) rather than ad-hoc DDL.
- **Cache / rate limiting** — Redis backs both the response cache
  (`flask-caching`) and the request-rate limiter (`flask-limiter`), with
  an automatic in-memory fallback if Redis is unreachable so the API
  degrades gracefully instead of failing outright.
- **Ingestion job (`backend/utils/ingest_agmarknet.py`)** — pulls crop
  price data from the official data.gov.in API mirror of Agmarknet on a
  schedule and loads it into Postgres, fuzzy-matching crop/market names
  against existing records.
- **AI assistant (`backend/services/rag.py`, `services/llm.py`)** — a
  lightweight retrieval-augmented endpoint: it matches crop/state/district
  names mentioned in a question against the DB, retrieves the relevant
  recent price records, and asks an LLM to answer strictly from that data.
  Falls back to a plain "latest record" response when no LLM key is
  configured.
- **Anomaly & forecast utilities (`backend/utils/anomaly.py`,
  `forecast.py`)** — rule-based deviation-from-trailing-average and
  least-squares trend calculations (not ML models), used by the
  anomalies and forecast endpoints.

### Infrastructure & deployment

- **Primary (Azure)** — provisioned via Terraform (`terraform/`):
  Resource Group, Azure Container Registry, PostgreSQL Flexible Server,
  Azure Cache for Redis, a Log Analytics workspace, and a Container Apps
  Environment running the backend and frontend containers.
- **CI/CD** — GitHub Actions (`.github/workflows/ci-cd.yml`, mirrored by
  `azure-pipelines.yml` for Azure DevOps shops) runs a secret scan,
  backend/frontend tests and dependency/vulnerability scans, builds and
  pushes Docker images to ACR, scans images for vulnerabilities, and
  deploys to Container Apps on merge to `main`.
- **Scheduled jobs** — a separate workflow
  (`.github/workflows/ingest-and-backup.yml`) runs nightly to pull fresh
  price data and back up the database.
- **Disaster recovery (AWS)** — a cost-conscious "backup + redeploy"
  pattern (`aws-dr/`): nightly encrypted `pg_dump` backups pushed to an
  S3 bucket, with a documented `restore.sh` runbook that stands up an RDS
  Postgres instance and redeploys the backend (mirrored to ECR) if Azure
  becomes unreachable.
- **Local development** — `docker-compose.yml` runs the full stack
  (Postgres, Redis, backend, frontend) locally in one command.

