# Project Context — AI Chatbot Portal (Thai Citizen Guide)

> Primary orientation doc for this repo. Loaded into every session via `CLAUDE.md` (`@context.md`).
> Keep it current: **after any completed code change, update this file, commit, and (on merge to `main`) rebuild docker compose.**

## What this is

An **AI gateway / one-stop-service portal** that routes Thai citizens' natural-language
questions to the relevant Thai government agencies and returns a synthesized answer.
Product-facing name has been rebranded **"AI Chatbot Portal"** (backend `APP_NAME`, frontend UI);
the repo and `README.md` still carry the original **"Thai Citizen Guide"** name.

A citizen asks a question → the orchestrator decomposes it into sub-questions →
dispatches them to matching agencies over **API / MCP / A2A** → synthesizes the
agency responses into one LLM-written answer with citations. An admin dashboard
manages agencies, health, analytics, users/roles, API keys, and LLM routing.

The heavy orchestration (decompose → route → dispatch → synthesize, sync **v3** and
streaming **v4**) runs in an **external OneChat service** (`ONECHAT_V3_URL` / `ONECHAT_V4_URL`).
This backend is the **portal/gateway**: it wraps OneChat, exposes its own MCP server of
agency data that OneChat calls back into, persists conversations, and provides all the
admin/analytics/auth surface.

## Services (docker-compose.yaml)

All traffic enters through **nginx** on one port; services talk over the `chatbot-network`.

| Service | Tech | Role |
|---|---|---|
| **nginx** | nginx | Reverse proxy, single external port `EXTERNAL_HTTP_PORT`. Routing in `default.conf`. |
| **backend** | Python 3.12 · FastAPI · Tortoise ORM · FastMCP | REST API (`/api/v1`), MCP server (`/mcp`), scheduler, auth. Port 8080. |
| **agent-proxy** | Go 1.26 · pgx · OTel | Caching reverse-proxy from backend → agency endpoints; logs connection attempts. Port 8080. |
| **frontend** | React 18 · Vite 5 · TS · shadcn/ui | SPA admin + public portal. Port 8080. |
| **postgres** | pgvector/pgvector:pg16 | Shared DB (backend + agent-proxy). Extensions: `pg_trgm`, `fuzzystrmatch`, `vector` (created by `postgres-init`). |
| **redis** | redis:7-alpine | Distributed rate limiting (optional; empty `REDIS_URL` = in-process limiter). |
| **jaeger** | jaegertracing/jaeger:2.18.0 | OTLP tracing sink (`jaeger:4317`), UI proxied at `/jaeger/`. |

**nginx routing (`default.conf`, single source of truth):**
- `/api`, `/sse`, `/messages`, `/mcp`, `/docs`, `/redoc`, `/openapi.json` → `backend:8080`
- `/agent-proxy/` → `agent-proxy:8080`
- `/jaeger/` → `jaeger:16686`
- `/` (everything else) → `frontend:8080` (SPA)

`docker-compose.override.yaml` adds dev watch/rebuild rules per service.

## Request flow (chat)

`POST /api/v1/chat` (sync) and `POST /api/v1/chat/stream` (SSE) live in
`backend/app/routers/chat.py`.

1. **Rate limit + quota** (`services/rate_limit.py`, `services/quota.py`): per-user RPM
   (`USER_RATE_LIMIT_RPM`, default 30), per-user monthly token quota, global daily USD budget.
   Anonymous callers skip these; over-limit → HTTP 429 + `Retry-After`.
2. **Similarity cache** (new conversations only): `services/similarity.py`
   `find_similar_question()` uses **`pg_trgm`** trigram similarity (`SIMILARITY_THRESHOLD` 0.95,
   `SIMILARITY_WINDOW_SECONDS` 3 days) over prior successful turns. Hit → copy cached answer
   (no new ConnectionLog, so copies never re-cache). Vector embeddings were removed in favor of
   `pg_trgm` (migration `19_..._drop_embedding_add_pg_trgm`); the `vector` extension is installed
   but not currently used for chat similarity. Note: `Conversation.status="failed"` is a one-way
   ratchet, so failed turns never poison the cache.
3. **Dispatch to OneChat**: sync `/chat` → `chat_external()` POSTs `ONECHAT_V3_URL`;
   `/chat/stream` proxies `ONECHAT_V4_URL` SSE, re-emitting `answer`/`error`/`done` events.
   Payload includes `mcp_endpoint_url` so OneChat can call back into agency MCP tools.
   Existing conversations first do `ensure_session_warmed()` (`services/session.py`).
4. **Persist**: `services/chat/turn.py::save_turn()` writes Conversation + user/assistant
   Messages + a `ConnectionLog` (action=`query`).
5. **Classify** (background task): `services/chat/llm.py::classify_message_category()` tags the
   turn with a Thai category via the classification LLM.

In-process agency dispatch (API/MCP/A2A) also exists in `services/chat/dispatch.py`
(retry/backoff, per-agency timeouts) — used for the direct-orchestration path.

## Backend (`backend/`)

FastAPI app wired in `app/main.py`; config in `app/config.py` (pydantic-settings
`Settings`, plus DB-persisted overrides via the `Setting` model & `/settings` page).
Lifespan runs: assert prod secrets → init DB → load DB settings → seed admin & agencies →
start scheduler → mount MCP. `uvicorn --workers 4` in prod, so MCP runs **stateless-http**.

**Package map (`app/`):**
- `routers/` — 18 REST routers, all mounted under `/api/v1`: `auth`, `users`, `agencies/`
  (package: `crud`, `golden`, `lifecycle`, `owners`, `spec`), `conversations`, `messages`,
  `chat`, `dashboard`, `feedback`, `connection_logs`, `api_key`, `executive_summary`,
  `insight`, `public_status`, `popular_questions`, `settings`, `audit_log`, `llm`.
  (`seed` router is not mounted.) `popular_questions` exposes anonymous
  `GET /public/popular-questions` + admin CRUD `/popular-questions` + `POST …/regenerate` (202).
  `public_status` also exposes anonymous `GET /public/agencies` — a display-safe agency directory
  (id/name/short_name/logo/description/connection_type/status, non-draft only; no internals) that
  feeds the portal's หน่วยงานที่เชื่อมต่อ block.
- `models/` — Tortoise ORM (see Data model).
- `schemas/` — Pydantic request/response models.
- `services/` — domain logic: `agency*` (health, lifecycle, reconcile, conformance),
  `chat/` (dispatch, llm, turn), `analytics/` (brief, dashboard, health), `similarity`,
  `quota`, `rate_limit`, `circuit_breaker`, `session`, `evaluation`, `mcp_discovery`,
  `usage_context`, `log_sanitize`, `audit`, `cache_flush`, `user`.
- `auth/` — `security.py` (bcrypt, JWT, API-key hashing), `dependencies.py` (auth + RBAC
  chokepoint), `authz.py` (ReBAC relationship checks).
- `mcp/` — FastMCP `server.py` (exposes `list_agency` tool / `agencies://list` resource,
  API-key authed) and `client.py`.
- `scheduler.py` — APScheduler jobs (see below).
- `concurrency.py`, `database.py`, `errors.py` (unified error envelope), `utils/` (uuid7, retry).

**Scheduler jobs (`app/scheduler.py`):**
- `agency_chat_test` every `HEALTH_CHECK_INTERVAL_MINUTES` (15): POST-probes each non-draft/
  non-disabled agency (omits the `__query__` field on purpose to observe missing-field
  handling; content rules whitelist e.g. "Message is required"→success), logs to
  `ConnectionLog`, then `reconcile_statuses()`. Concurrency capped by `AGENCY_CHAT_CONCURRENCY`.
- `regenerate_brief_job` every `BRIEF_REGEN_INTERVAL_HOURS` (24) — weekly executive brief.
- `purge_old_connection_logs` every 24h (`CONNECTION_LOG_RETENTION_DAYS`, 90).
- `run_evaluation` every `EVAL_INTERVAL_HOURS` (168 / weekly) — golden-question LLM-judge eval.
- `regenerate_popular_questions` every `POPULAR_QUESTIONS_REGEN_INTERVAL_HOURS` (24): LLM-synthesizes
  clean คำถามยอดนิยม (purpose `popular_questions`) from successful user turns in the last
  `POPULAR_QUESTIONS_WINDOW_DAYS` (30). No-ops below `POPULAR_QUESTIONS_MIN_TURNS` (20) so the
  dopa/dol/fda seed shows on a fresh deploy. Churn: replaces only unpinned/unhidden `auto` rows;
  seed/manual/pinned/hidden untouched; hidden `text_key`s act as tombstones (never regenerated).

**External integrations (config.py):** OpenRouter (`CLASSIFICATION_MODEL`
`google/gemini-2.5-flash-lite`), ThaiLLM parse-spec endpoint, OneChat v3/v4, MCP endpoint.
LLM providers/models are now also DB-configurable via `LlmProvider`/`LlmRoute` (admin pages):
a `LlmRoute` maps a `purpose` (e.g. `classification`, `brief`, `judge`, `parse_spec`,
`popular_questions`) to a provider + model. Route resolution is cached (~30s) and invalidated on any provider/route mutation.

**Tests:** pytest (`asyncio_mode=auto`, `backend/tests/`), httpx AsyncClient transport.

## Data model (Tortoise ORM, `app/models/`)

| Model | Table | Purpose / key fields |
|---|---|---|
| `Agency` | `agencies` | Government agency. `connection_type` (API/MCP/A2A), `status` (draft/active/maintenance/disabled), `auto_maintenance`, `endpoint_url`, `expected_payload` (placeholder JSON), `api_headers`, `data_scope`, routing (`priority`, `router_hint`, `dispatch_timeout_s`, `mcp_tool_name`), `conformance_report`, metrics (`total_calls`, `rating_up/down`), `stats_reset_at`. |
| `User` | `users` | Account. `role` = `user|viewer|auditor|agency_owner|admin`, bcrypt `hashed_password`, reset-token fields. |
| `UserAPIKey` | `user_api_keys` | Programmatic keys. `key_hash` (only hash stored), `key_prefix`, `expires_at`, `revoked_at`, per-key `rate_limit_rpm`, `last_used_at`. Keys are prefixed **`tcg_`**. |
| `Conversation` | `conversations` | Chat session. `title`/`preview`, `agencies` (names), `status`, `message_count`, `external_session_id`, FK `user` (SET_NULL). |
| `Message` | `messages` | Turn message. `role`, `content`, `agent_steps`, `sources`, `rating`, `feedback_text`, `category` (Thai), `agency_ids`, `errors`, `parent_id`. |
| `ConnectionLog` | `connection_logs` | Every agency call/probe. `action` (test/query), `connection_type`, `status`, `latency_ms`, sanitized `request_body`/`response_body`, `message_id`/`assistant_message_id` (links to Message; enables cache). |
| `GoldenQuestion` / `EvalResult` | `golden_questions` / `eval_results` | Per-agency QA regression set + LLM-judge scores. |
| `ExecutiveBrief` | `executive_briefs` | Generated weekly narrative brief. |
| `LlmProvider` | `llm_providers` | LLM service (name, base_url, api_key, auth, rate limits, enabled). |
| `LlmRoute` | `llm_routes` | Maps a `purpose` (classification/synthesis/router/…) → provider + `model` (+ timeout). |
| `LlmUsage` | `llm_usage` | Token/cost tracking per call, dimensioned by user/agency/conversation/api_key. |
| `AuditLog` | `audit_logs` | Admin actions; denormalized `actor_email` survives user deletion. |
| `Relationship` | `relationships` | ReBAC tuples: subject → `relation` (owner/viewer) → object (agency/conversation). |
| `Setting` | `settings` | Runtime config overrides (key/value/type/group/is_secret), loaded at startup over env defaults. |
| `PopularQuestion` | `popular_questions` | คำถามยอดนิยม shown on portal/chat. `text`, unique normalized `text_key` (dedupe + hidden-tombstone), nullable `agency` FK (SET_NULL), `source` (seed/auto/manual), `pinned`, `hidden`, `sort_order`, `score`. Published = not-hidden, pinned→sort_order→score→recency, capped `POPULAR_QUESTIONS_DISPLAY_COUNT` (8). |

Migrations: **aerich** (`backend/migrations/`, 21 applied). **Never hand-carry `MODELS_STATE`** —
always regenerate via `aerich migrate` against an upgraded DB. See `docs/aerich-migrations.md`
and the mandatory rules in `CLAUDE.md`.

## Auth & RBAC

- **Bearer token** = JWT (from `POST /api/v1/auth/login`) **or** a `tcg_` API key. Both resolve
  through `app/auth/dependencies.py::_resolve_token`. Optional-auth endpoints (chat, conversations)
  allow anonymous, but a **bad `tcg_` key is rejected (401)** rather than silently degrading.
  Any **`GET` under `/api/v1/public/`** (e.g. `public_status`, `popular_questions`) is exempt from
  the role chokepoint for **every** role — the shared frontend `apiClient` attaches the JWT on all
  requests, so an authenticated `user`/`viewer` hitting a public GET must not 403. Keep routers under
  that prefix strictly read-only.
- **Roles**: `user` (chat + architecture list), `viewer` (read-only operational/analytics pages),
  `auditor` (read-only everything except Settings), `agency_owner` (self-service own agencies),
  `admin` (full). Enforced by a **global chokepoint** `enforce_role_allowlist` (allowlists per role
  in `dependencies.py`); `admin`/`agency_owner`/anonymous pass through to per-endpoint guards
  (`require_admin`, `require_admin_or_auditor`, ReBAC in `authz.py`).
- **MCP mount is intentionally outside** the role chokepoint (mounted sub-app bypasses FastAPI
  deps); MCP auth is by API key in `mcp/server.py` — any active user, no role check. See the big
  comment in `main.py` and `tests/test_mcp_role_access.py` before touching this.

## agent-proxy (`agent-proxy/`, Go)

Reverse proxy between backend and agency endpoints. `POST /agent-proxy/{agencyID}` looks up the
agency's `endpoint_url` + `api_headers` (cached in-memory, TTL `AGENCY_CACHE_TTL` default 60s;
`store.go` reads shared postgres via `DATABASE_URL`), forwards the request, writes a
`connection_logs` row, and increments `agencies.total_calls`. Exports spans to Jaeger. `GET /health`.

## Frontend (`frontend/`, React SPA)

React 18 + Vite 5 + TypeScript, **shadcn/ui** (Radix + Tailwind), **TanStack Query**, **axios**,
**react-router-dom v6**, react-hook-form + zod. **Feature-based** layout under `src/features/*`
(one dir per page: chat, dashboard, executive, health, heatmap, agencies, history, architecture,
connection-logs, api-keys, settings, llm-providers, llm-routes, popular-questions, users, audit,
usage, feedback, public, status, auth). Shared code in `src/shared/*`. Package manager = **pnpm** (Dockerfile uses
`pnpm --frozen-lockfile`; stray `bun.lock`/`package-lock.json` are not authoritative).

- **API layer** (`shared/lib/apiClient.ts`): axios, base URL `VITE_API_BASE_URL` (defaults to
  `window.location.origin` → same-origin via nginx). Request interceptor attaches JWT from
  `localStorage['auth_token']`; response interceptor unwraps the `{error:{message}}` envelope
  (with legacy `detail` fallback).
- **Auth**: `features/auth/useAuth` + `ProtectedRoute`. Public routes: `/`, `/about`,
  `/data-policy`, `/contact`, `/status`, `/login`, `/signup`, `/forgot-password`, `/reset-password`.
  Authenticated routes are role-gated in `App.tsx`, mirroring backend RBAC (e.g. `/chat` +
  `/architecture` any role; `/settings`, `/llm-providers`, `/llm-routes`, `/popular-questions`
  admin-only). The portal/chat คำถามยอดนิยม block is fed by the anonymous
  `GET /public/popular-questions` (no more hardcoded `suggestedQuestions` in `mockData.ts`).
  The public portal's หน่วยงานที่เชื่อมต่อ block (`AgencyCards` + `usePublicAgencies`) is fed by
  the anonymous `GET /public/agencies`.
- **Chat streaming** (`features/chat/chatApi.ts`): consumes `/chat/stream` SSE via native `fetch`
  (events `step`, `agencies`, `intent`, `routing`, `agency_start`, `agency_responded`,
  `agency_verified`, `answer`, `done`, `error`), with a per-chunk idle timeout and a JSON-polling
  fallback. Message rating uses optimistic UI updates.
- **Serve**: multi-stage Dockerfile → `vite build` → static `dist/` served by nginx
  (`frontend/nginx.conf`, SPA fallback). Container healthcheck hits **`/healthz`** (not `/health`,
  which is a client route).
- `frontend/supabase/` is **vestigial** (legacy edge functions/migrations; not referenced by `src`;
  the app talks only to the FastAPI backend).
- **Tests**: vitest + jsdom + **MSW** (`src/mocks`, `src/test`). `VITE_USE_MOCKS=true` enables MSW in
  the browser for mock-backed local runs.

## Infrastructure, CI/CD, deployment

- **Branches**: `main` = prod (protected, **PR-only**, deploys to prod), `dev` = dev env.
  Branch off `dev` → PR into `dev`; promote via PR `dev` → `main`. Never push `main` directly.
- **`.github/workflows/test.yml`** (on PR / manual): parallel jobs — backend `pytest` (with redis
  service), agent-proxy `go build && go test`, frontend `tsc --noEmit` + vitest coverage. **No E2E**
  (removed from CI).
- **`.github/workflows/deploy.yml`** (merged PR to `main` / manual): self-hosted runner, validates
  `JWT_SECRET`/`OPENROUTER_API_KEY`, writes prod `.env` (`ENV=production`), then
  `docker compose up -d --build --remove-orphans`. Deploy does **not** depend on the test job.
- **Prod env** template: `.env.prod.example` (set `JWT_SECRET`, `POSTGRES_PASSWORD`, `CORS_ORIGINS`,
  OneChat URLs, `OPENROUTER_API_KEY`). `ENV=production` makes startup refuse the default JWT secret.

## Testing suites

- **backend/tests** — pytest, in-process httpx AsyncClient.
- **blackbox/** — vitest API-contract tests: a role × endpoint/page access matrix
  (`src/access-matrix.ts`); only 401/403 responses fail. Seeds `bb-<role>` users. Needs a running
  stack + existing admin (`admin@example.com`/`admin1234` default).
- **e2e/** — Playwright, drives the real SPA per role (login → visit entitled pages → assert no
  redirect and no 401/403 in background calls). Reuses blackbox provisioning. **Not run in CI.**

## Agency integration contract (for `examples/reference-agency`)

An `API` agency exposes an HTTP `POST` endpoint. The gateway builds the body from
`expected_payload` with placeholder substitution (`__query__`, `__session_id__`,
`__conversation_id__`, `__user_id__`) and sends `api_headers` (lowercased) + `content-type: json`.
**Return HTTP 200 for every valid question** (non-2xx = error contribution). Before `draft → active`,
an agency must pass a **5-check conformance battery**: `responds`, `non_empty`, `thai_text`,
`concurrency_3`, `garbage_input` (stored in `agency.conformance_report`). Transient errors retry up
to 3× with backoff; 4xx/5xx do not. `MCP` and `A2A` connection types are also supported.
Full spec: `docs/agency-integration.md`; API-consumer guide: `docs/quickstart.md`.

## Documentation & specs map

- `docs/quickstart.md` — API consumer flow (get `tcg_` key, auth, `/chat`, `/chat/stream`, errors,
  rate limits).
- `docs/agency-integration.md` — agency endpoint contract, health probes, conformance.
- `docs/aerich-migrations.md` — migration discipline (never fake `MODELS_STATE`).
- `spec/roadmap.md` — product vision & phased roadmap (security → cost tracking → reliability →
  chat consolidation → agency self-service/authz → trust/quality).
- `spec/v4-streaming.md`, `spec/mcp-server.md`, `spec/agent-*.md` — OneChat v4 SSE event spec, MCP
  server contract, and orchestrator/agency integration notes.
  ⚠️ `spec/agent-20260623.md`, `agent-onechat.md`, `agent-promes.md` contain **real agency/Dify API
  keys flagged for rotation** — treat as secrets, do not propagate.

## Conventions & gotchas

- After any completed code change: **update this `context.md`, then commit**; on merge to `main`,
  **rebuild docker compose**.
- **Multi-task work → create a branch first** (`feat/`, `fix/`, `chore/`, `refactor/`); never commit
  multi-step work to `main`. Do **not** use claude worktree.
- **TDD is mandatory** (red → green → refactor). Go changes: run `/use-modern-go`, then gofmt +
  `golangci-lint run --allow-parallel-runners` (repeat until clean).
- Prefix all shell commands with **`rtk`** (token-optimizing proxy) — see `docs/rtk.md`.
- Agencies router registers literal paths (`/mine`, `/mcp/discover`, `/parse-spec`) **before**
  parametric `/{agency_id}` to avoid UUID wildcard shadowing (`routers/agencies/__init__.py`).
- Error responses use a unified envelope `{"error":{"code","message","retryable","upstream_status"}}`
  (`app/errors.py`); frontend unwraps it, with legacy `detail` fallback.
