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

```mermaid
flowchart LR
    user(["👩‍🌾 Farmer / User<br/>(mobile or desktop browser)"])

    subgraph azure["☁️ Azure — Primary (Container Apps Environment)"]
        direction LR
        fe["<b>Frontend</b><br/>React 18 SPA served by nginx<br/>i18n: Hindi · Telugu · English"]

        subgraph be["<b>Backend</b> — Flask REST API (app.py factory)"]
            direction TB
            mw["Cross-cutting middleware<br/>ProxyFix · CORS allow-list · Rate limiter<br/>Security headers · JSON error handlers"]
            r1["routes/prices.py<br/>/api/states · districts · crops<br/>/api/prices · prices/trend<br/>/api/prices/anomalies · prices/forecast<br/>/api/health"]
            r2["routes/assistant.py<br/>POST /api/ask"]
            u["utils/anomaly.py · utils/forecast.py<br/>(rule-based, explainable)"]
            rag["services/rag.py<br/>entity matching + retrieval"]
            llm["services/llm.py<br/>Anthropic Messages client"]
            orm["SQLAlchemy models<br/>+ Alembic migrations"]
            mw --> r1
            mw --> r2
            r1 --> u
            r2 --> rag --> llm
            r1 --> orm
            rag --> orm
        end

        pg[("<b>PostgreSQL</b><br/>Flexible Server<br/>states · districts · markets<br/>crops · price_records")]
        redis[("<b>Redis</b><br/>Azure Cache<br/>response cache + rate-limit counters<br/>(in-memory fallback)")]
        logs["Log Analytics"]
    end

    claude["🤖 Anthropic Claude API<br/>(optional — only if ANTHROPIC_API_KEY is set)"]

    subgraph ingest["⏰ Nightly job — GitHub Actions (01:00 UTC)"]
        job["utils/ingest_agmarknet.py<br/>fuzzy-match crops / markets → upsert"]
    end
    govt["🏛️ data.gov.in<br/>Agmarknet open API"]

    subgraph aws["☁️ AWS — Disaster Recovery"]
        s3[("S3 bucket<br/>encrypted pg_dump backups<br/>versioned + lifecycle")]
        ecr["ECR<br/>backend image mirror"]
        rds["RDS Postgres<br/>(created only on restore)"]
    end

    user -- "HTTPS" --> fe
    fe -- "/api/* reverse-proxy" --> mw
    orm <--> pg
    mw <-. "cache · rate limit" .-> redis
    llm -- "HTTPS (grounded prompt)" --> claude
    be -. "logs" .-> logs

    govt -- "pull daily prices" --> job
    job -- "writes" --> pg
    job -. "after ingest" .-> s3
    pg -- "nightly pg_dump" --> s3
    s3 -. "restore.sh" .-> rds
    ecr -. "redeploy backend" .-> rds
```

### Request flow — price lookup (cached read path)

```mermaid
sequenceDiagram
    autonumber
    actor U as Farmer
    participant FE as React SPA (nginx)
    participant API as Flask API
    participant R as Redis
    participant DB as PostgreSQL

    U->>FE: Pick state / district / crop (Hindi, Telugu or English)
    FE->>API: GET /api/prices?state_id=…&crop_id=…&lang=hi
    API->>API: Rate-limit check (60/min)
    API->>R: Lookup cache key (query string)
    alt Cache hit (≤ 15 min old)
        R-->>API: Cached JSON
    else Cache miss
        API->>DB: Join price_records → markets → districts → states
        DB-->>API: Latest-date rows (paged)
        API->>R: Store response (15 min TTL)
    end
    API-->>FE: JSON (names localised via name_hi / name_te)
    FE-->>U: Price table / cards + trend chart
```

### Request flow — AI assistant (grounded RAG)

```mermaid
sequenceDiagram
    autonumber
    actor U as Farmer
    participant FE as AskAssistant.jsx
    participant API as POST /api/ask
    participant RAG as services/rag.py
    participant DB as PostgreSQL
    participant LLM as Anthropic Claude

    U->>FE: "आज गुंटूर में टमाटर का भाव?"
    FE->>API: { question, lang }
    API->>API: Validate (≤ 500 chars) + rate-limit (10/min)
    API->>RAG: answer_question()
    RAG->>DB: Fuzzy-match crop / state / district names
    RAG->>DB: Fetch matching PriceRecords (last 14 days, up to 30 rows)
    alt API key configured
        RAG->>LLM: System prompt + retrieved records (answer ONLY from data)
        LLM-->>RAG: Short answer in requested language
    else No key / LLM error
        RAG-->>API: Plain "latest record" fallback
    end
    API-->>FE: { answer, matched, records_used, assistant_enabled }
    FE-->>U: Answer shown in chat panel
```

### Delivery pipeline & environments

```mermaid
flowchart LR
    dev["Developer<br/>push / PR"] --> gh["GitHub Actions<br/>ci-cd.yml<br/>(mirrored by azure-pipelines.yml)"]

    subgraph checks["Quality & security gates"]
        direction TB
        g1["gitleaks<br/>secret scan"]
        g2["pytest + Jest"]
        g3["pip-audit · npm audit"]
        g1 --> g2 --> g3
    end

    gh --> checks --> build["Docker multi-stage builds<br/>backend + frontend"]
    build --> trivy["Trivy image scan"] --> acr["Azure Container Registry"]
    acr -- "merge to main" --> ca["Azure Container Apps<br/>backend + frontend"]

    tf["Terraform<br/>terraform/ (Azure) · aws-dr/ (AWS)"] -. "provisions" .-> ca
    tf -. "provisions" .-> pgr["PostgreSQL · Redis · Log Analytics"]

    local["docker-compose.yml<br/>Postgres + Redis + backend + frontend"] -. "local dev" .-> dev
```

### Data model

```mermaid
erDiagram
    STATE ||--o{ DISTRICT : has
    DISTRICT ||--o{ MARKET : has
    MARKET ||--o{ PRICE_RECORD : reports
    CROP ||--o{ PRICE_RECORD : priced_as

    STATE { int id PK
            string name_en
            string name_hi
            string name_te }
    DISTRICT { int id PK
               string name_en
               int state_id FK }
    MARKET { int id PK
             string name_en
             int district_id FK }
    CROP { int id PK
           string name_en
           string category }
    PRICE_RECORD { int id PK
                   int market_id FK
                   int crop_id FK
                   string variety
                   string grade
                   decimal min_price
                   decimal max_price
                   decimal modal_price
                   date price_date
                   string source }
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

## Security

### Secrets management

- No credentials are hardcoded in application code. Local secrets are
  supplied via a `.env` file (gitignored, based on `.env.example`); in
  CI/CD and production they come from GitHub Actions secrets and
  Container App secrets.
- `SECRET_KEY` fails loudly at startup in production if it isn't set,
  rather than silently falling back to a default value — the app refuses
  to boot instead of running insecurely.
- The `ANTHROPIC_API_KEY` and `DATA_GOV_IN_API_KEY` are optional at
  runtime: their absence disables the related feature (AI assistant /
  live ingestion) instead of crashing the app.

### Application-layer protections

- **CORS** is restricted to an explicit allow-list (`CORS_ORIGINS`)
  rather than `*`.
- **Rate limiting** (`flask-limiter`) protects the public API from
  scraping/abuse, backed by Redis with an in-memory fallback so limiting
  stays active even during a Redis outage.
- **Security headers** are set on every response: `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, a restrictive
  `Content-Security-Policy`, and `Strict-Transport-Security` in
  non-debug mode.
- The app trusts exactly one reverse-proxy hop (`ProxyFix`), so
  rate-limiting and logging see the real client IP rather than the
  proxy's.

### CI/CD security checks

- Every push/PR runs a **secret-scanning** job (gitleaks) before any
  build or deploy step.
- **Dependency vulnerability scans** run on both backend (`pip-audit`)
  and frontend (`npm audit`) dependencies.
- **Container image scanning** (Trivy) checks built images for known
  CVEs before deployment.

### Data protection

- DR backups to S3 are server-side encrypted (SSE-AES256) and lifecycle
  managed (old versions expire automatically).
- Redis connections in production use TLS (`rediss://`).
- Database credentials and connection strings are injected as Container
  App secrets, not stored in Terraform state as plain variables or
  committed to the repo.

### Known hardening follow-ups

These need real cloud account access to do safely and aren't implemented
in this repo yet:

- Move DB/Redis connection strings out of Terraform-interpolated
  Container App secrets and into Azure Key Vault references.
- Restrict the Postgres flexible server firewall rule (currently open to
  any Azure tenant) to a VNet/private endpoint.
- Switch ACR auth from admin username/password to managed identity.
- Replace the long-lived `AZURE_CREDENTIALS` / AWS access-key GitHub
  secrets with OIDC federated login for both clouds.
- Put a WAF / Azure Front Door in front of the public Container App
  ingress.
- Encrypt DR backups with a customer-managed KMS key instead of relying
  solely on S3's default SSE-S3.

## Why this application is different from other applications

Most mandi/crop-price tools fall into one of two buckets: an official
government portal that's data-complete but hard to use, or a scraper-based
third-party app that's easier to use but built on fragile, unofficial data
collection. This project is designed to sit in neither bucket.

- **Sourced from the official API, not scraped.** Agmarknet's own website
  is notoriously difficult to query programmatically. Instead of scraping
  HTML (which breaks on every markup change and is a legal/ToS grey area),
  `backend/utils/ingest_agmarknet.py` pulls from the official data.gov.in
  API mirror of the same dataset — a stable, sanctioned, structured data
  source. Most third-party price apps take the scraping shortcut; this one
  deliberately doesn't.

- **Built for the farmer reading it, not just the data.** The UI defaults
  to **Hindi**, not English, with Telugu also supported and more languages
  addable by extending one resources object (`frontend/src/i18n`). Most
  agricultural data portals — government and private alike — are
  English-first with regional language support as an afterthought, if it
  exists at all. This flips that default.

- **Mobile-first for low-bandwidth users.** Large touch targets, a price
  table that collapses into cards on narrow screens, and a minimal JS
  bundle — built on the assumption that the target user is on a mid-range
  Android phone on a patchy mobile connection, not a desktop browser on
  fiber.

- **Explains *why* a price looks unusual, instead of just listing it.**
  The `/api/prices/anomalies` endpoint flags prices that deviate sharply
  from a market's trailing 7-day average — the kind of signal that helps a
  farmer spot when a middleman is quoting a suspiciously low price. Plain
  price-listing apps show the number; this one also flags when the number
  looks wrong.

- **An AI assistant that's grounded, not generative.** `/api/ask` doesn't
  let an LLM freely answer price questions from its own "knowledge" (which
  would risk confidently inventing a price). It retrieves the actual
  matching `PriceRecord`s from the database first, and instructs the model
  to answer *only* from that retrieved data — a deliberate RAG design
  rather than a chatbot bolted on for its own sake. It also degrades
  gracefully: with no API key configured, the endpoint still returns a
  plain "latest record" answer instead of failing.

- **Deviation-based and trend-based, not black-box ML — on purpose.** Both
  anomaly detection and price forecasting use transparent, explainable
  methods (trailing-average deviation; least-squares trend fitting)
  instead of an opaque ML model. At this data volume, a rule a farmer or
  developer can actually read and verify is more trustworthy than a model
  that's marginally more accurate but impossible to explain — see the
  docstrings in `backend/utils/anomaly.py` and `forecast.py`.

- **Resilient by design, not just by scale.** Redis-backed caching and
  rate limiting both fall back to in-memory alternatives automatically if
  Redis is unreachable, so a cache outage degrades performance rather than
  taking the whole API down — a distinction many small-to-mid apps skip.

- **Honest, right-sized disaster recovery.** Rather than marketing
  always-on multi-cloud redundancy it doesn't need, this project is
  explicit about its actual DR posture: nightly encrypted backups to AWS
  S3 plus a documented, scripted restore runbook, with a stated RPO of
  ~24h and RTO of ~1-2h. That's a deliberate cost/benefit call for a
  public-good transparency site, stated plainly instead of oversold.

- **Security treated as a default, not an add-on.** Secret scanning,
  dependency and container image scanning run on every CI build; the app
  fails to start in production without a real `SECRET_KEY` instead of
  silently using an insecure default; and standard hardening (CORS
  allow-list, security headers, rate limiting) ships out of the box
  rather than being left for a "someday" security pass. See the
  Security section above.

