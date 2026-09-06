# Mandi Bhav — Crop Price & Mandi Transparency Platform

A vernacular-language website showing daily mandi (market) crop prices by
crop and district, sourced from government open data (Agmarknet /
data.gov.in), so farmers can check the real market price before selling to
a middleman.

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

> Note: you listed AngularJS under Frontend and ReactJS separately — this
> scaffold builds the **React** frontend, since AngularJS (1.x) is a legacy
> framework Google stopped supporting in 2022 and isn't a great fit for a
> new project. Say the word if you actually want an AngularJS build instead
> or in addition.

## Why this design

- **Vernacular-first**: the UI defaults to Hindi, not English, with Telugu
  also supported (`frontend/src/i18n`) — add more languages by extending
  that resources object.
- **Mobile-first, low-bandwidth**: large touch targets, table collapses
  into cards on narrow screens, minimal JS bundle.
- **Government data, not scraped**: `backend/utils/ingest_agmarknet.py`
  pulls from the official data.gov.in API mirror of Agmarknet rather than
  scraping the (notoriously clunky) Agmarknet website directly.
- **Cache-first API**: Redis caches every read endpoint so thousands of
  farmers hitting the same district/crop query doesn't hammer Postgres.
- **Cheap, honest DR**: rather than pretending to run always-on multi-cloud
  replication for a public-good site, DR is nightly encrypted backups to
  AWS S3 plus a documented restore runbook (`aws-dr/restore.sh`) — an
  RPO of ~24h and RTO of ~1-2h, which is the right cost/benefit for this
  kind of project.

## Project layout

```
backend/            Flask API, SQLAlchemy models, Agmarknet ingestion job
frontend/            React app (i18n, filters, price table)
terraform/           Azure infra (Resource Group, ACR, Postgres, Redis, Container Apps)
aws-dr/               AWS backup bucket + restore runbook (DR)
.github/workflows/    CI/CD + daily ingestion & backup
azure-pipelines.yml    Equivalent pipeline for Azure DevOps shops
docker-compose.yml     Full local stack
```

## Run it locally

```bash
cp .env.example .env    # add a data.gov.in API key if you have one (optional for demo)
docker compose up --build

# in another terminal, seed demo data so the UI has something to show
docker compose exec backend python seed_data.py
```

- Frontend: http://localhost:8080
- Backend API: http://localhost:5000/api/health

Without a `DATA_GOV_IN_API_KEY`, the ingestion job simply skips itself —
use `seed_data.py` for local development/demo data instead. Get a free key
at https://data.gov.in/user/register, then look for the
"Variety-wise Daily Market Prices Data of Commodity" dataset (or Agmarknet
directly) and set `DATA_GOV_IN_RESOURCE_ID` if it differs from the default.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/states?lang=hi` | list states |
| `GET /api/districts?state_id=&lang=` | list districts |
| `GET /api/crops?lang=` | list crops |
| `GET /api/prices?crop_id=&district_id=&state_id=&date=&lang=&page=&per_page=` | daily prices, paginated |
| `GET /api/prices/trend?crop_id=&market_id=&days=30` | price history for a sparkline |
| `GET /api/prices/anomalies?state_id=&district_id=&deviation_pct=25` | prices that deviate sharply from a market's trailing 7-day average |
| `GET /api/prices/forecast?crop_id=&market_id=&days_ahead=7` | short-term linear-trend price projection, with a confidence score |
| `POST /api/ask` | natural-language Q&A over the price data (RAG + Claude); `{"question": "...", "lang": "hi"}` |

Full spec: [`openapi.yaml`](./openapi.yaml).

## AI assistant (`/api/ask`)

A small retrieval-augmented endpoint: it fuzzy-matches crop/state/district
names mentioned in the question against what's actually in the DB, pulls
the last 14 days of matching `PriceRecord`s, and asks Claude to answer
*only* from that retrieved data (never invents a price). Set
`ANTHROPIC_API_KEY` (get one at https://console.anthropic.com/) to enable
it — without a key the endpoint still responds, just with a plain
"latest record" fallback instead of an LLM-generated answer, so it's safe
to ship before a key is provisioned.

Anomaly detection and forecasting are deliberately **not** ML models —
rule-based deviation-from-trailing-average and least-squares trend
fitting respectively. See the docstrings in `backend/utils/anomaly.py`
and `backend/utils/forecast.py` for why that trade-off makes sense at
this data volume.

## Database migrations

Schema changes are managed with Flask-Migrate (Alembic), not
`db.create_all()`/`drop_all()` (those remain in `seed_data.py`, which is
demo-only and drops all data):

```bash
cd backend
flask db upgrade          # apply all migrations to the current DATABASE_URL
flask db migrate -m "..."  # after changing models.py, generate a new migration
```

## Running tests

```bash
# backend — no live Postgres/Redis needed, falls back to in-memory SQLite
cd backend && pip install -r requirements-dev.txt && pytest -q

# frontend
cd frontend && npm install && CI=true npm test -- --watchAll=false
```

## Deploying to Azure

```bash
cd terraform
terraform init
terraform apply \
  -var="container_registry_name=mandiappacr" \
  -var="postgres_admin_password=<strong-password>"
```

Then push images (CI/CD does this automatically on merge to `main`):

```bash
az acr login --name mandiappacr
docker build -t mandiappacr.azurecr.io/mandi-backend:latest ./backend
docker push mandiappacr.azurecr.io/mandi-backend:latest
docker build -t mandiappacr.azurecr.io/mandi-frontend:latest ./frontend
docker push mandiappacr.azurecr.io/mandi-frontend:latest
```

Required GitHub Actions secrets: `ACR_NAME`, `ACR_USERNAME`, `ACR_PASSWORD`,
`AZURE_CREDENTIALS`, `PROD_DATABASE_URL`, `PROD_REDIS_URL`,
`DATA_GOV_IN_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_BACKUP_BUCKET`, `ANTHROPIC_API_KEY` (optional — enables the `/api/ask`
assistant; the app runs fine without it).

## Disaster recovery (AWS)

```bash
cd aws-dr
terraform init && terraform apply   # creates S3 backup bucket + ECR mirror
```

The `ingest-and-backup.yml` workflow runs nightly: pulls fresh Agmarknet
data into the primary Postgres DB, then dumps and uploads it to S3. If
Azure becomes unreachable, follow `aws-dr/restore.sh` to stand the site
back up on AWS.

## Roadmap ideas (not built yet)

- SMS/IVR price alerts for farmers without smartphones (e.g. via a
  gateway like Exotel/Twilio) — the highest-impact next feature.
- Price-trend push notifications ("onion prices in your district rose 12%
  this week").
- More regional languages (Marathi, Tamil, Punjabi, Kannada, Bengali).
- A user-facing "report a suspicious price" community flag, complementing
  the automated `/api/prices/anomalies` detection now in place.
- Swap the rule-based `/api/prices/forecast` for a proper time-series
  model once there's enough historical depth (months, not weeks) to
  justify one.
- Cloud hardening items that need real account access to do safely —
  see "Known follow-ups" below.

## Known follow-ups (need real cloud credentials — not done in this repo)

- Move DB/Redis connection strings out of Terraform-interpolated Container
  App secrets and into Azure Key Vault references.
- Restrict the Postgres flexible server firewall rule (currently
  `allow_azure_services`, open to any Azure tenant) to a VNet/private
  endpoint.
- Switch ACR auth from admin username/password to managed identity.
- Replace the long-lived `AZURE_CREDENTIALS` / `AWS_ACCESS_KEY_ID` GitHub
  secrets with OIDC federated login for both clouds.
- Put a WAF / Azure Front Door in front of the public Container App
  ingress.
- Encrypt DR backups with a customer-managed KMS key instead of relying
  solely on S3's default SSE-S3.

