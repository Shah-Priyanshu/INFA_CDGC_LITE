# Copilot instructions for CDGC‑Lite

Use `cdgc_lite_detailed_technical_plan_industry_standard.md` as the source of truth. The following are the standard stack choices and canonical workflows for this repo.

## Standard stack decisions
- Backend: FastAPI + Pydantic + Postgres (Alembic migrations)
- Workers: Celery with Redis (ElastiCache) as broker/result backend (industry‑standard, rich ecosystem)
- Frontend: React + Vite + TypeScript + MUI
- Infra: Terraform → AWS ECS Fargate, RDS Postgres, ElastiCache Redis, S3, CloudFront, Route53
- Auth: Azure AD (Microsoft Entra ID) via OIDC/JWT; issuer `https://login.microsoftonline.com/<tenant-id>/v2.0`, audience `api://cdgc-lite`

## Architecture shape
- APIs: `/healthz`, `/readyz`, CRUD for `system|asset|column`, FTS search, lineage (`/lineage/sql`, `/lineage/graph`), glossary, classification.
- Connectors: Snowflake, Postgres, S3 with `discover()` + `harvest()`; incremental via `last_seen_at`; persist raw payloads to `scan_artifact`.
- Workers: `scan_job` model; retries/backoff; idempotent `POST /ingest/<source>/scan`.

## Data model & migrations
- Core tables: `system`, `asset`, `column`, `lineage_edge`, `scan_artifact`, `scan_job`, `glossary_term`; soft‑delete via `deleted_at`.
- Alembic: expand → migrate → contract; always set `down_revision` for zero‑downtime.

## Search/FTS pattern (Postgres)
- Use generated column `search_vector` = `to_tsvector('simple', unaccent(coalesce(name,'')||' '||coalesce(description,'')||' '||coalesce(column_names,'')))` with GIN index.
- Query with `plainto_tsquery('simple', unaccent(:q))`; include highlight fragments in API response.
 - Highlight example: `ts_headline('simple', coalesce(description,''), plainto_tsquery('simple', unaccent(:q)))`

## Versions & env
- Versions: Python 3.11; Node 20.x; Postgres 15; Redis 7
- Compose service names: `db`, `redis`, `api`, `worker`, `ui`
- Required .env (root): `DATABASE_URL`, `REDIS_URL`, `OIDC_ISSUER`, `OIDC_AUDIENCE`, `AZURE_CLIENT_ID` (API), `SECRET_KEY`, optional `SENTRY_DSN`

### Python environment (venv)
- Always use a project-local virtual environment. **Do not use the system/root Python.**
- Create and activate venv:
	- Windows (PowerShell):
		- `python -m venv .venv`
		- `.\.venv\Scripts\Activate.ps1`
	- macOS/Linux (bash/zsh):
		- `python3 -m venv .venv`
		- `source .venv/bin/activate`
- Upgrade pip and install deps into the venv:
	- `python -m pip install --upgrade pip`
	- `python -m pip install -r requirements-dev.txt`
	- `python -m pip install -r backend/requirements.txt -r workers/requirements.txt`

## Canonical local commands (compose services: db, redis, api, worker, ui)
- Ensure your venv is activated before running any Python-based command below.
- DB up/migrate: `docker compose up -d db redis`; `alembic upgrade head`
	- Note: `alembic` resolves from the active venv; alternatively use `python -m alembic upgrade head`.
- API: `python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`
- Worker: `python -m celery -A workers.app worker -l info`
- Frontend: `npm install`; `npm run dev` (Vite)
- Tests: `python -m pytest -q`; target coverage ≥85%; integration via Testcontainers
- Lint/type/security (from venv):
	- `python -m ruff check .`
	- `python -m black --check .`
	- `python -m isort --check-only .`
	- `python -m mypy .`
	- `python -m bandit -r .`
	- `semgrep --config auto` (or install via venv and use `python -m semgrep --config auto`)
	- `detect-secrets scan` (or `python -m detect_secrets scan` if installed via venv)

## CI/CD toolchain
- CI: build → lint → tests → Docker → SBOM (Syft) → scan (Trivy) → sign (cosign) → push; upload artifacts
- Deploy: on merge to `main` deploy to dev (Terraform apply, migrations, smoke, seed); manual promote to stage/prod (blue/green)
- AWS access via OIDC (no long‑lived keys); rate limits 100 req/min (dev), 1000 (prod); redact sensitive logs

## Integration specifics
- Snowflake: `information_schema` + `account_usage`; parse `query_history` with `sqlglot` (Snowflake dialect) → `lineage_edge` with confidence
- S3/Parquet: extract schema + partitions; Postgres connector mirrors Snowflake discovery/profiling

## Contribution conventions
- Branches `feat|fix|chore/<scope>`; Conventional Commits; labels `area:{api,ui,infra,conn,lineage}`; senior review required for API/DB changes; ADRs for irreversible decisions
