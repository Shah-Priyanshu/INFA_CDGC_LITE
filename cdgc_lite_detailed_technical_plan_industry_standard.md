# CDGC‑Lite: Detailed Development Plan

## Phase 1: Project Setup & Foundations (Week 1)
- **Repository Initialization**: Create monorepo structure with `backend/`, `frontend/`, `connectors/`, `workers/`, `infra/`, and `docs/` directories.
- **Version Control & Branching**: GitHub repo with `main`, `dev`, and feature branches; enforce PR reviews.
- **CI/CD Skeleton**: GitHub Actions for lint, tests, and Docker build; pre‑commit hooks with ruff, black, isort, mypy, detect‑secrets.
- **FastAPI Bootstrapping**: Hello world endpoint, Pydantic models, OpenAPI spec auto-generation.
- **Database Setup**: Postgres + Alembic migrations for base tables (`system`, `asset`, `column`).
- **Authentication Stub**: OAuth2/JWT with placeholder scopes.

## Phase 2: Metadata Core (Week 2)
- Implement CRUD APIs for `system`, `asset`, and `column` with search and pagination.
- Integrate Postgres full-text search for `asset` and `column`.
- Unit tests for repository and API layers.

## Phase 3: Snowflake Connector (Week 3)
- Build `discover()` and `harvest()` for Snowflake using `information_schema` and `account_usage`.
- Add incremental scan logic with `last_seen_at`.
- Store raw ingestion payloads in `scan_artifact`.
- Celery/Arq worker for async scans.
- Integration tests using Snowflake test account.

## Phase 4: Lineage MVP (Week 4)
- Parse Snowflake queries via `sqlglot` to map source→target columns.
- Create `lineage_edge` table and API to fetch lineage graph.
- Visualize lineage in a simple D3.js or Recharts view in UI.

## Phase 5: Glossary & Classification (Week 5)
- CRUD for `glossary_term` and term linking to assets/columns.
- Implement regex-based PII detectors for email, phone, DOB.
- API for running classification on selected columns.
- Unit tests for detectors and classification scoring.

## Phase 6: UI MVP (Week 6)
- React frontend: login, search page, asset detail, lineage graph, glossary term linking.
- Connect frontend to backend APIs.
- Apply MUI components and responsive design.

## Phase 7: Hardening & Observability (Week 7)
- Implement RBAC with roles (`viewer`, `steward`, `engineer`, `admin`).
- Add audit logging for all write operations.
- Set up Prometheus metrics for API and workers.
- k6 load testing; optimize queries and indexes.
- Write user/admin documentation in MkDocs.

## Phase 8: Deployment (Week 8)
- Terraform scripts for AWS ECS Fargate, RDS Postgres, ElastiCache Redis, S3, CloudFront, and Route53.
- Deploy backend, frontend, and workers to ECS.
- Configure CloudWatch dashboards and alerts.
- Seed demo dataset and record screencast demo.

## Ongoing: Quality & Governance
- Maintain ≥85% test coverage.
- Weekly backlog grooming; address ADRs for architectural decisions.
- Review and merge PRs with security scanning and code reviews.
- Keep documentation updated with each feature change.



---

## 22) Comprehensive Development Plan

### A. Delivery Strategy
- **Methodology:** Scrum‑ish, 1‑week sprints; trunk‑based development with short‑lived feature branches; Continuous Delivery to **dev**; manual approval gates to **stage**/**prod**.
- **Environments:**
  - **Local:** Docker Compose; ephemeral Postgres/Redis/MinIO.
  - **Dev:** ECS Fargate single‑AZ, RDS t‑class; public endpoint; demo data auto‑seeded.
  - **Stage:** Multi‑AZ, mirrors prod sizing at 50%; realistic datasets; load testing permitted.
  - **Prod:** Multi‑AZ, change windows, blue/green deploys.
- **Branching:** `main` (protected) → release tags; feature branches `feat/<scope>`; `fix/<scope>`; `chore/<scope>`; squash merge; Conventional Commits.
- **Definition of Ready (DoR):** Problem statement, acceptance criteria, test notes, observability notes, security notes, estimated effort.
- **Definition of Done (DoD):** Code, tests, docs, lint clean, threat checks passed, telemetry added, feature flags where applicable, deployment verified, rollback plan documented.

### B. Roles & RACI (minimal team)
- **Tech Lead (you):** Architecture, code reviews, ADRs, release approvals. *(A/R)*
- **Backend Eng:** FastAPI, connectors, lineage engine, APIs. *(R)*
- **Frontend Eng:** React UI, lineage graph, search UX. *(R)*
- **DevOps Eng:** Terraform, CI/CD, observability, security baselines. *(R)*
- **Data Steward (proxy):** Glossary, classification policy, UAT. *(C)*

### C. Work Breakdown Structure (WBS)
**Epic 1 – Repo & Platform Bootstrap**
1. **INFRA‑001** Terraform root modules (VPC, subnets, NAT, SGs). *3d*
2. **CI‑001** GitHub Actions: build→test→scan→docker→SBOM→sign→push. *1d*
3. **API‑000** FastAPI skeleton, `/healthz`, `/readyz`, OpenAPI. *1d*
4. **DB‑000** Postgres + Alembic baseline; migrations pipeline. *1d*
5. **OBS‑000** OTel/JSON logging; log correlation IDs; Sentry hook. *1d*
6. **SEC‑000** AuthN stub (OAuth/OIDC), RBAC scaffold, secret loading. *2d*

**Epic 2 – Metadata Core**
1. **DB‑101** Create tables: `system`, `asset`, `column`, indices. *2d*
2. **API‑101** CRUD endpoints + pagination + search on assets/columns. *2d*
3. **API‑102** FTS on name/description/column names; highlight fragments. *1d*
4. **WRK‑101** Celery/Arq workers, job model `scan_job`. *1d*
5. **OBS‑101** Metrics: asset counts, job durations, error rates. *0.5d*

**Epic 3 – Connectors**
1. **CONN‑SF‑001** Snowflake discovery (`information_schema`). *3d*
2. **CONN‑SF‑002** Snowflake profiling (rowcount/null%). *1d*
3. **CONN‑PG‑001** Postgres discovery/profiling. *2d*
4. **CONN‑S3‑001** S3/Parquet schema extraction + partitions. *2d*
5. **API‑201** `POST /ingest/<source>/scan` + idempotency keys. *1d*
6. **WRK‑201** Retry/backoff, incremental `last_seen_at`, artifacts store. *1d*

**Epic 4 – Lineage MVP**
1. **LIN‑001** SQL parser integration (`sqlglot` Snowflake dialect). *2d*
2. **LIN‑002** Column dependency graph; edge confidence & predicates. *3d*
3. **LIN‑003** Ingest Snowflake `query_history`; filter/normalize. *2d*
4. **LIN‑004** REST endpoints `/lineage/sql`, `/lineage/graph` (depth/hops). *2d*
5. **LIN‑005** Rendering service contract for UI. *0.5d*

**Epic 5 – Glossary & Classification**
1. **GLO‑001** Glossary CRUD; term linking to assets/columns. *2d*
2. **CLS‑001** Rule‑based detectors (email/phone/dob/cc luhn). *2d*
3. **CLS‑002** Scoring + severity; override workflow + audit. *2d*
4. **POL‑001** Minimal policy DSL + evaluate endpoint. *2d*

**Epic 6 – UI MVP**
1. **WEB‑001** React app scaffold (Vite, TS, MUI, routing, auth). *2d*
2. **WEB‑002** Global search + results list with filters. *2d*
3. **WEB‑003** Asset detail (schema, columns, terms, classifications). *3d*
4. **WEB‑004** Lineage graph view (D3/Recharts), hop control, highlights. *3d*
5. **WEB‑005** Term pages + approval flows. *2d*

**Epic 7 – Hardening & Docs**
1. **SEC‑101** Least‑priv Snowflake role; rotate keys; CSP/HSTS. *1d*
2. **QA‑001** Playwright E2E, contract tests, k6 baseline. *3d*
3. **DOC‑001** MkDocs site; Quickstart; Admin Guide; API cookbook. *2d*
4. **REL‑001** Release process, changelog automation, versioning. *0.5d*

**Epic 8 – Deploy & Demo**
1. **REL‑002** ECS services (api, worker, ui), ALB, scaling policies. *2d*
2. **DATA‑DEMO** Seed demo datasets + dbt manifest ingestion. *1d*
3. **UAT‑001** Stakeholder walkthrough; bug bash; sign‑off. *1d*

> *Estimates assume 1–2 engineers; adjust by team size. Parallelize where safe (e.g., UI with API mocks).* 

### D. Backlog → Tickets Template
**Title:** `<scope>: concise action`
**Description:** Context, requirements, non‑goals
**Acceptance Criteria:** Gherkin‑style Given/When/Then
**Security Notes:** authZ/PII/secret handling
**Observability Notes:** metrics/logs/traces added
**Tests:** unit/integration/E2E list
**Out of Scope:** explicit

### E. Quality Gates & Policies
- **PR Rules:** ≥1 senior reviewer for API/DB changes; mandatory architectural label `api|db|ui|infra`.
- **Static Checks:** ruff/black/isort/mypy/bandit/semgrep in CI; coverage ≥85%.
- **Secrets Policy:** no plaintext keys; commit hooks + detect‑secrets; break‑glass runbook.
- **Artifact Supply Chain:** SBOM (Syft), image scan (Trivy), cosign attestations; deny on critical vulns.

### F. CI/CD Pipelines (GitHub Actions)
**1) `ci.yml` (push/PR):**
- Setup Python/Node → lint → unit tests (pytest) → integration tests via Testcontainers → build Docker images → scan (Trivy) → SBOM → upload artifacts.

**2) `deploy-dev.yml` (on merge to main):**
- Build & push images → Terraform plan/apply to `dev` → run migrations → smoke tests (`/healthz`) → seed demo data → notify Slack.

**3) `promote.yml` (manual):**
- Fetch release image SHAs → Terraform plan/apply to `stage`/`prod` → blue/green swap → run k6 + Playwright smoke → finalize.

> Add environments protection rules, reviewers, and OIDC‑based federation to AWS (no long‑lived keys).

### G. Security & Privacy Baselines
- Threat model doc (STRIDE) per epic; track mitigations.
- PII handling: default **off** for sampling; redact logs; configurable allowlist for profiling.
- Rate limits: `/api` 100 req/min/IP dev, 1000 prod; exponential backoff on 429.
- Audit every mutate endpoint with actor, target, diff, IP; tamper‑evident via hash chain (optional v1.1).

### H. Observability Plan
- **Metrics:** API latency (p50/95), error %, job success %, queue depth, ingestion lag.
- **Logs:** JSON; request IDs; user/tenant IDs (where applicable); sensitive data redaction.
- **Traces:** OTel spans for connectors, SQL parse, DB calls; sampling 10% dev, 1% prod.
- **Dashboards:** API SLI, Workers SLI, DB health; Alerts on SLO breaches (+ paging schedule).

### I. Data & Migration Strategy
- Alembic migrations with `down_revision`; zero‑downtime schema changes (expand→migrate→contract).
- Data backfill jobs for assets on connector improvements; version raw artifacts for reproducibility.
- Soft‑delete assets (`deleted_at`), GC after retention; lineage edge rebuild jobs.

### J. Risk Register (live)
- **R1:** SQL lineage false positives → mitigate with conservative heuristics + manual override UI.
- **R2:** Connector API limits → implement paging/throttling + circuit breakers.
- **R3:** Cost creep on ECS/RDS → budgets + autoscaling + sleep dev cluster off‑hours.
- **R4:** Security regressions → mandatory checks + quarterly pen‑test checklist.

### K. Pilot/UAT Plan
- Select 2 subject areas (e.g., `CUSTOMERS`, `ORDERS`).
- Success Criteria: searchable within 1s; accurate lineage on top 20 queries; detectors ≥90% precision on rule‑based PII; zero P1 defects.
- UAT Scripts: discovery, lineage trace, classification override, policy evaluation, approval workflow.

### L. Communication & Governance
- Weekly demo; RFCs for cross‑cutting changes; ADRs for irreversible decisions.
- Release cadence: weekly tagged releases (semantic versioning) with changelog.
- Issue labels: `type:{feat,bug,chore,docs}`, `area:{api,ui,infra,conn,lineage}`, `risk:{low,med,high}`.

### M. 90‑Day Timeline (sample)
**Weeks 1–2:** Epics 1–2 complete to dev; CI solid; basic search.
**Weeks 3–4:** Snowflake connector + lineage MVP; initial UI screens.
**Weeks 5–6:** Glossary + classification; UI lineage; stage env up.
**Weeks 7–8:** Hardening, docs, k6 baseline, UAT; prod deploy; v1.0 tag.

### N. Exit Criteria for v1.0
- All v1 endpoints stable and documented.
- Connectors: SF, PG, S3 functional with retries & incremental scans.
- Lineage confidence displayed; override UI shipped.
- RBAC minimal roles; audit on all mutations.
- SLOs met for 14 consecutive days in stage.

