# Agency Management Redesign — Backend (Sub-project 2) — Design

**Date:** 2026-06-11
**Status:** Approved (user: "implement all")
**Branch:** `feat/agency-backend-contract` (builds on the `AgencyStatus` enum fix)

## Goal

Implement, in the FastAPI backend, the API contract that sub-project 1's MSW
mock layer already defines, so the redesigned agency UI works against the real
backend: persist the new routing/MCP fields, expose embedded health + a health
history endpoint, add status-transition and MCP-discovery endpoints, health-check
all three connection types, and feed routing controls into the chat router.

The frontend's MSW handlers (`frontend/src/mocks/handlers.ts`) and fixtures are
the authoritative contract. All response field names are snake_case and must
match what the frontend's `mapRowToAgency` / `mapBucketRow` read.

## Reused existing machinery (no rebuild)

- **Routing already filters `status="active"`** (`app/services/chat/graph.py:26`),
  so draft/maintenance/disabled are excluded for free.
- **`app/services/analytics.py::get_agency_health`** already aggregates uptime /
  latency / error-rate / hourly history per agency from `ConnectionLog`. Health
  is computed from `ConnectionLog`; **no new table**.
- **`app/services/agency.py::test_connection`** probes all three protocols
  (`_test_rest` HEAD, `_test_mcp` JSON-RPC initialize, `_test_a2a` POST). The
  scheduler reuses it to health-check MCP/A2A.
- **`app/mcp/client.py`** (`fastmcp.Client`) provides `list_tools()` for discovery.
- Migrations are **Aerich** (`aerich migrate --name X` → `aerich upgrade`).

## Contract (must match the frontend exactly)

### Agency row (snake_case) — new fields
- `priority: int | null`
- `router_hint: str` (default `""`)
- `dispatch_timeout_s: int | null`
- `mcp_tool_name: str | null`
- `rating_up: int`, `rating_down: int` (already on the model; add to response)
- `health: { state, uptime_24h, avg_latency_ms_24h, last_check_at } | null`
  - `state ∈ {"up","degraded","down","unknown"}`
  - numeric fields and `last_check_at` are null when no checks exist.

### Endpoints
- `GET /api/v1/agencies` and `GET /api/v1/agencies/{id}` — each agency includes the
  new fields and embedded `health`.
- `GET /api/v1/agencies/{id}/health/history?window=24h|7d|30d` →
  `{ data: [{ bucket_start, uptime_pct, avg_latency_ms, checks, failures }] }`.
  Hourly buckets for 24h/7d, daily for 30d. 404 if agency missing.
- `PATCH /api/v1/agencies/{id}/status` — body `{ status }`; enforces the same
  legal-transition table as the frontend; `422` with `{ detail }` containing the
  word "transition" on an illegal move; returns the updated agency row.
- `POST /api/v1/agencies/mcp/discover` — body `{ endpoint_url }` →
  `{ tools: [{ name, description, input_schema }] }`; `422` if `endpoint_url`
  missing; `502`-style error surfaced as `{ detail }` on connection failure.
- `POST` / `PATCH /api/v1/agencies` — accept the new fields; `POST` already
  tolerates partial config for `status="draft"` (the enum fix shipped that).

### Legal transitions (mirror `frontend/src/features/agencies/lifecycle.ts`)
```
draft       → active, disabled
active      → maintenance, disabled
maintenance → active, disabled
disabled    → active
```

## Health derivation (from ConnectionLog, per agency)

Over a 24h window of that agency's `ConnectionLog` rows (`action` test or query):
- `total` = count, `failures` = count where `status != "success"`.
- `uptime_24h = round((total-failures)/total*100, 1)` (null if `total == 0`).
- `avg_latency_ms_24h = round(AVG(latency_ms))` (null if `total == 0`).
- `last_check_at` = max(`created_at`) (null if none).
- **state**:
  - `unknown` if `total == 0`.
  - `down` if the most-recent row's `status != "success"`.
  - `degraded` if last row ok but `uptime_24h < settings.HEALTH_DEGRADED_UPTIME_PCT` (default 95.0).
  - `up` otherwise.

This is a new, focused helper (`app/services/agency_health.py`) returning the
embedded-health dict in the exact contract shape — distinct from the existing
camelCase `get_agency_health()` (which powers the separate insights page and is
left unchanged).

## Architecture / file changes

- **`app/models/agency.py`** — add `priority`, `router_hint`, `dispatch_timeout_s`,
  `mcp_tool_name` columns.
- **`migrations/models/4_*.py`** — Aerich migration: add the 4 columns; data step
  `UPDATE agencies SET status='disabled' WHERE status='inactive'` (downgrade
  reverses to `inactive`).
- **`app/schemas/agency.py`** — add the new fields to `AgencyBase`/`AgencyUpdate`;
  add `rating_up`/`rating_down`/`health` to `AgencyResponse`; add `AgencyHealthEmbed`,
  `HealthHistoryBucket`, `HealthHistoryResponse`, `StatusUpdateRequest`,
  `McpDiscoverRequest`, `McpToolInfo`, `McpDiscoverResponse`.
- **`app/services/agency_health.py`** (new) — `embedded_health(agency_id)` and
  `health_history(agency_id, window)` aggregating ConnectionLog.
- **`app/services/agency_lifecycle.py`** (new) — `LEGAL_TRANSITIONS` + `is_legal`.
- **`app/services/mcp_discovery.py`** (new) — `discover_tools(endpoint_url)` via
  `fastmcp.Client.list_tools()`.
- **`app/routers/agencies.py`** — inject embedded health into list/get; add
  `/{id}/health/history`, `/{id}/status`, `/mcp/discover`; persist new fields in
  create/update.
- **`app/scheduler.py`** — extend `agency_chat_item` to health-check MCP and A2A
  agencies via `test_connection` (writing ConnectionLog), keeping the existing
  API real-query path. Skip `draft`/`disabled` agencies.
- **`app/services/chat/llm.py`** — `build_router_prompt` includes `router_hint`
  when present.
- **`app/services/chat/graph.py`** — enrich routes with `priority` +
  `dispatch_timeout_s`; sort dispatched routes by `priority` (nulls last).
- **`app/services/chat/dispatch.py`** — use per-agency `dispatch_timeout_s` when
  set, else the global setting.
- **`app/config.py`** — `HEALTH_DEGRADED_UPTIME_PCT: float = 95.0`.

## Testing (TDD, pytest, in-memory SQLite `db` fixture)

Note: the existing `get_agency_health` uses Postgres-only `RawSQL`
(`TO_CHAR`, `SET TIME ZONE`). The new `agency_health` helpers must be written to
run under the SQLite test DB — use the Tortoise ORM aggregation API
(`annotate(Count/Avg/Sum)`, `.order_by`) rather than Postgres-specific SQL, or
keep raw SQL portable. Tests seed `ConnectionLog` rows directly.

- `agency_lifecycle`: legal/illegal transition matrix.
- `agency_health.embedded_health`: unknown (no logs); up; degraded (uptime below
  threshold); down (last log failed); uptime/latency math.
- `agency_health.health_history`: bucket counts per window; bucket fields.
- Router `create`/`patch`: new fields persist; `GET` returns them + health.
- `PATCH /status`: legal applies; illegal → 422 with "transition".
- `POST /mcp/discover`: missing endpoint_url → 422; success maps tools (mock the
  fastmcp client); connection error → error detail.
- Scheduler: MCP/A2A agencies get a ConnectionLog entry (mock `test_connection`);
  draft/disabled skipped.
- Router prompt: includes router_hint; routes sorted by priority; dispatch uses
  per-agency timeout (assert the value passed).

## Verification
- `cd backend && .venv/bin/python -m pytest tests/ -q` — all green.
- `cd backend && .venv/bin/python -c "from app.main import app"` — imports.
- `aerich upgrade` applies cleanly on a Postgres dev DB (documented; CI uses SQLite).

## Out of scope
- Frontend changes (sub-project 1 is complete and already on its own branch).
- Replacing the existing camelCase `get_agency_health` / insights page.
- Real load/perf tuning of the scheduler concurrency semaphore.
