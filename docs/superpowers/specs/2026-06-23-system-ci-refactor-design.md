# System / CI / Infra Hygiene Refactor Design

**Date:** 2026-06-23
**Goals:**
- **Work** — run *all* existing tests in CI (frontend vitest is written but never executed) and add a real pre-deploy gate so a merge to `main` cannot deploy a red build.
- **Right** — drive hardcoded config/secrets out of source into env/secrets; document the nginx routing contract and the agent-proxy↔backend seam; make healthchecks consistent.
- **Fast** — cache uv / go / pnpm dependencies and Docker layers; parallelize and gate jobs so the slow e2e sweep runs only when fast checks pass.

This is the **system seam**. Component-internal work is owned by the sibling 2026-06-23 specs (`2026-06-23-agent-proxy-refactor-design.md`, and the backend/frontend 2026-06-23 specs). This spec changes the *pipeline and infra around* the apps — no application behavior changes except those explicitly listed under Behavior Changes.

## Context

The monorepo composes five first-party build targets (postgres, redis, backend, agent-proxy, frontend) behind an nginx gateway, plus a Jaeger sidecar. CI is three GitHub Actions workflows. Measured today (every claim below was read from the actual files, not an external assessment):

- Frontend has 30 `*.test.{ts,tsx}` files and a `"test": "vitest run"` script — **CI never runs them**; the frontend job only runs `pnpm exec tsc --noEmit`.
- `deploy.yml` deploys on PR-merged-to-`main` (self-hosted runner) with **no `needs:` gate** — tests passing is not a precondition.
- `test-e2e.yaml` triggers only on `pull_request → main` (plus `workflow_dispatch`/`workflow_call`); the daily `dev` flow never exercises the full stack sweep.
- A live OpenRouter key sits in the on-disk `.env` (gitignored, untracked — but real and must be rotated).
- Admin credentials `admin@example.com` / `admin1234` are baked into both workflow YAML and the committed `*.env.test.example` files.
- `backend/app/config.py` hardcodes deployment-specific URLs/IPs as defaults (`ONECHAT_V3_URL`/`V4_URL` → `185.84.160.55`, `MCP_ENDPOINT_URL` → `185.84.161.145`, `CORS_ORIGINS`, `FRONTEND_BASE_URL`).
- Two nginx files exist with different roles but **no documented routing contract**.
- Healthcheck targets differ in path and host across services.
- Only the frontend CI job caches deps; backend (uv) and agent-proxy (go) re-resolve every run.

## Current Composition (as measured)

### Services & dependency graph

```
postgres (pgvector/pgvector:pg16, healthcheck: pg_isready)
  └─ postgres-init (postgres:16, runs CREATE EXTENSION pg_trgm/fuzzystrmatch/vector, then exits)
redis (redis:7-alpine, healthcheck: redis-cli ping)
backend (build ./backend target=production)
  depends_on: postgres(healthy), postgres-init(completed), redis(healthy)  — all restart:true
agent-proxy (build ./agent-proxy target=production)
  depends_on: postgres(healthy)
frontend (build ./frontend target=production)  — static SPA served by its own nginx
nginx (image nginx, mounts ./default.conf)  — the GATEWAY
  depends_on: frontend(healthy), backend(healthy), agent-proxy(healthy), jaeger(started)
  ports: ${EXTERNAL_HTTP_PORT}:8080
jaeger (jaegertracing/jaeger:2.18.0, base_path=/jaeger)
```

All services share `chatbot-network`. `docker-compose.override.yaml` flips backend/agent-proxy/frontend to `target=development` and adds `develop.watch` for hot reload. `docker compose up` merges both; CI/prod use `-f docker-compose.yaml` alone.

### Routing — TWO nginx configs, different jobs (not duplicates)

The two files are frequently mistaken for duplication. They are not:

| File | Container | Role |
|------|-----------|------|
| `./default.conf` | `nginx` gateway | Reverse proxy: routes `/api`,`/sse`,`/messages`,`/mcp`,`/docs`,`/redoc`,`/openapi.json` → backend; `/agent-proxy/` → agent-proxy; `/jaeger/` → jaeger; `/` → frontend |
| `frontend/nginx.conf` | inside `frontend` image | Static SPA server: serves `/usr/share/nginx/html`, SPA fallback to `index.html`, asset caching, security headers, `/healthz` |

Both `listen 8080`. The gateway's `location /` forwards to the frontend container's nginx, which then does SPA fallback. The genuine problem is the **routing contract is undocumented** and the two files drift independently. Decision: keep both files (they have distinct responsibilities) but add a header comment in each pointing to the other and to a single source-of-truth routing table in this spec.

Gateway routing contract (canonical):

```nginx
# ./default.conf — gateway, listen 8080
location ~ ^/(api|sse|messages|mcp|docs|redoc|openapi.json)  -> http://backend:8080
location /agent-proxy/                                        -> http://agent-proxy:8080
location /jaeger/                                             -> http://jaeger:16686
location /                                                    -> http://frontend:8080  (SPA)
```

### Healthchecks (inconsistent — measured)

| Service | Test | Path returns |
|---------|------|--------------|
| postgres | `pg_isready -U $USER -d $DB` | — |
| redis | `redis-cli ping` | — |
| backend | `wget -q -O /dev/null http://localhost:8080/health` | FastAPI `/health` → `"ok\n"` |
| agent-proxy | `wget -q -O /dev/null http://localhost:8080/health` | Go `/health` → `"ok\n"` |
| frontend | `wget -q -O /dev/null http://127.0.0.1:8080/healthz` | nginx `/healthz` → `"ok\n"` |
| jaeger | none (`condition: service_started` only) | — |

Inconsistencies: frontend uses `127.0.0.1` + `/healthz` while backend/agent-proxy use `localhost` + `/health`; intervals/start_period vary (frontend `start_period: 5s`, backend `30s`). `wget` availability is fine: frontend prod is `nginx:alpine` and agent-proxy prod is `alpine` — both ship busybox `wget`. Backend prod installs `wget` explicitly. Decision: standardize host to `127.0.0.1`, keep each service's real health path (the SPA cannot serve `/health` — it would shadow the Agency Health client route, per the existing comment in `frontend/nginx.conf`), and align interval/timeout/retries.

### Agent-proxy ↔ backend seam (measured)

`agent-proxy/main.go` serves `/agent-proxy/` (handler) and `/health` on `:8080`, exports OTLP traces to `jaeger:4317`, and reads only `DATABASE_URL`. It shares the postgres DB with the backend; there is no HTTP call from backend → agent-proxy in the gateway config — they are sibling services behind the same gateway, coupled through the shared database. This coupling is undocumented; the plan adds a short contract note.

## CI/CD Current State

| Workflow | Triggers | Jobs / what it runs | Gaps |
|----------|----------|---------------------|------|
| `test.yml` | `pull_request` (any), `push:[dev]`, `workflow_call` | **backend**: `uv sync --extra dev` + `uv run pytest -q` (redis service). **agent-proxy**: `go build ./... && go test ./...`. **frontend**: `pnpm install` + `tsc --noEmit` ONLY | Frontend **vitest never runs** (30 test files). No coverage. No caching for uv/go. Jobs already parallel (good). |
| `test-e2e.yaml` | `workflow_dispatch`, `workflow_call`, `pull_request:[main]` | `blackbox-e2e`: `docker compose up --build --wait`, wait for admin bootstrap, blackbox vitest API sweep, Playwright UI sweep. 30 min timeout. | Only on PR→`main`, never on PR→`dev`. Creds hardcoded in YAML. No docker layer cache → full rebuild each run. Single serial job. |
| `deploy.yml` | `pull_request:[main] closed` (merged) + `workflow_dispatch`, runs on `self-hosted` | Writes `.env`, `docker compose -f docker-compose.yaml up -d --build --remove-orphans` | **No test gate** (`needs:` absent) — a merged red PR still deploys. `.env` carries only `OPENROUTER_API_KEY`; all other secrets fall back to code defaults. |

Branch policy (from CLAUDE.md, must be respected): `main` = prod (deploy only via merged PR, never push directly); `dev` = dev env. Branch off `dev`, PR into `dev`; promote prod via PR `dev → main`.

## Work / Right / Fast Breakdown

### WORK — pipeline correctness
1. Run `frontend` vitest in CI (new step in `test.yml`).
2. Add a **pre-deploy gate**: `deploy.yml` `needs:` a reusable test workflow; deploy only if green.
3. Run the full-stack sweep (`test-e2e`) on PR→`dev` too, not just PR→`main`.
4. Stop shipping hardcoded admin creds in YAML — read from secrets.

### RIGHT — cohesion
1. De-hardcode `backend/app/config.py` deployment values; ship a `.env.prod.example` documenting them; deploy writes them from secrets.
2. Rotate + remove the live OpenRouter key from the on-disk `.env`.
3. Document the nginx routing contract (cross-reference comments + the canonical table above); keep the two-file split.
4. Standardize healthcheck host/path/timing.
5. Add a one-paragraph agent-proxy↔backend seam note (shared DB, sibling-behind-gateway).

### FAST — pipeline speed
1. Cache uv (`~/.cache/uv` keyed on `uv.lock`) and Go modules/build cache (`actions/setup-go` cache or `actions/cache`).
2. Add Docker layer caching to `test-e2e` via `docker/build-push-action` + GHA cache (or `compose build` with buildx + `--cache-from/--cache-to type=gha`).
3. Gate the expensive sweep behind the fast `test.yml` job (`needs:`), so a fast failure short-circuits e2e.
4. Frontend vitest and tsc run in the same job (shared install) — no extra checkout/install cost.

## Behavior Changes (each documented)

| # | Change | Why | Risk / mitigation |
|---|--------|-----|-------------------|
| B1 | Frontend vitest runs in CI | Tests existed but were dead weight | A previously-passing PR may now fail if a test was already broken — fix or quarantine before merge |
| B2 | `deploy.yml` gated on tests passing | Red builds reached prod | Adds ~CI latency to deploy; acceptable for prod safety |
| B3 | `test-e2e` also runs on PR→`dev` | Dev never exercised full stack | Longer dev PR feedback; mitigated by `needs: test` short-circuit |
| B4 | Admin creds sourced from GH secrets, not literal YAML | Secret hygiene | Requires repo secrets `E2E_ADMIN_EMAIL`/`E2E_ADMIN_PASSWORD`/`E2E_TEST_USER_PASSWORD` set before merge |
| B5 | Backend deployment URLs/CORS become env-driven (defaults stay safe localhost) | No prod IPs in source | Deploy must now provide them; documented in `.env.prod.example` |
| B6 | Healthcheck host/path/timing standardized | Consistency, faster ready detection | Pure infra; verified with `docker compose config` + stack up |

No application request/response behavior changes. App contracts are owned by the sibling backend/frontend specs.

## Config / Secrets Migration

Values moving from source defaults to env/secrets (defaults remain present for local dev so `docker compose up` still works zero-config):

| Source today | Where it lives now |
|--------------|--------------------|
| `OPENROUTER_API_KEY` (live key in `.env`) | **Rotate immediately**; GH secret only; never on disk in repo |
| `CORS_ORIGINS` (config.py default) | `.env.prod.example` + deploy `.env` from `secrets.CORS_ORIGINS` |
| `FRONTEND_BASE_URL` | `.env.prod.example` + deploy secret |
| `ONECHAT_V3_URL`, `ONECHAT_V4_URL`, `MCP_ENDPOINT_URL` (185.84.x IPs) | `.env.prod.example` + deploy secrets |
| `JWT_SECRET` (`change-me…` default; `assert_production_secrets` already enforces non-default when `ENV=production`) | deploy secret; set `ENV=production` so the existing assert fires |
| admin creds in workflows | GH secrets `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` / `E2E_TEST_USER_PASSWORD` |

New committed file `.env.prod.example` documents every prod var with empty/placeholder values (no real secrets). The committed `*.env.test.example` files keep `admin@example.com`/`admin1234` only as *local* defaults with a comment that CI overrides them from secrets.

## Testing / CI Strategy

- **Single source of truth for tests**: `test.yml` stays the reusable unit/integration workflow (`workflow_call`), now including frontend vitest + coverage.
- **Coverage visibility**: `vitest run --coverage` (frontend) and `pytest --cov` (backend) emit summaries to the job log; enforcement starts as *report-only* (no hard threshold) to avoid blocking the first green build — a follow-up can ratchet a minimum.
- **Gate**: `deploy.yml` adds `needs:` on a reusable call to `test.yml` (fast) and `test-e2e.yaml` (full stack), so deploy runs only when both are green. Keep `workflow_dispatch` as a manual break-glass.
- **Sequencing for speed**: `test-e2e` declares `needs:` nothing at PR time but its workflow-level trigger fans out *after* `test.yml`; within deploy, `test → test-e2e → deploy` chain via `needs:`.
- **Characterization mindset**: we change *only* the pipeline/infra. If turning on a previously-dead test reveals a real app bug (B1), that fix belongs in the relevant component spec, not here — quarantine with `test.skip` + a tracking note if needed to keep this refactor shippable.

## Out of Scope
- Resource limits / autoscaling.
- Migrating off the self-hosted deploy runner.
- Multi-environment (staging) topology beyond existing dev/prod.
- Application logic changes (owned by sibling 2026-06-23 component specs).
