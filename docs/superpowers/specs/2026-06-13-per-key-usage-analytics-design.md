# Per-API-Key Usage Analytics — Design

**Date:** 2026-06-13
**Status:** Approved
**Branch:** `feat/per-key-usage-analytics`

## Problem

`LlmUsage` records token/cost for every LLM call but cannot be attributed to the
specific API key that drove the request. The model has `user_id`/`agency_id`/
`conversation_id` but no `api_key_id`, and one user may own several keys.

A secondary gap: the existing `user_id` column is mostly NULL in practice. The
LLM call sites (e.g. `services/chat/llm.py:110`) call `openrouter_chat(...)`
without passing `user_id`, so even user-level attribution is missing today.

## Goal

Surface per-API-key usage to admins (token + cost), and fix the `user_id`
attribution gap as part of the same write-path change.

## Decisions

- **Backend + frontend** — one cohesive feature, including an admin page.
- **Flat per-key totals** with a **UTC date-range filter** (consistent with the
  recent quota day-boundary tz fix). No per-key drill-down in this iteration.
- **Catch-all bucket** — all keyless usage (web/JWT sessions, anonymous chat, and
  historical rows) aggregates into one `"—" (web/session)` row so per-key totals
  reconcile with the global usage figure.
- **ContextVar over explicit threading** — attribution is set once in the auth
  dependency and read in the usage writer. Touches 2 files in the write path
  instead of threading a param through every call site, and repairs `user_id`
  for free.
- **Plain `UUIDField`, not `ForeignKeyField`** — matches the existing
  `user_id`/`agency_id` columns and avoids cascade-delete wiping usage history
  when a key is hard-deleted (billing/audit integrity).

## Design

### 1. Data model + migration

`backend/app/models/llm_usage.py` — add:

```python
api_key_id = fields.UUIDField(null=True)
```

One Aerich migration adds the nullable column. Historical rows remain NULL and
fall into the catch-all bucket. No backfill (the data does not exist
retroactively).

### 2. Write-path wiring (ContextVar)

New module `backend/app/services/usage_context.py`:

```python
from contextvars import ContextVar
from uuid import UUID

current_user_id: ContextVar[UUID | None] = ContextVar("current_user_id", default=None)
current_api_key_id: ContextVar[UUID | None] = ContextVar("current_api_key_id", default=None)
```

- **Set** in `auth/dependencies.py:_resolve_token`:
  - API-key branch sets both `current_user_id` and `current_api_key_id`.
  - JWT branch sets `current_user_id` only.
  - Anonymous leaves both at the `None` default.
  - Safe across requests: each FastAPI request runs in its own asyncio task,
    which copies the context, so writes are request-local.
- **Read** in `llm_client.py:_record_usage`: read `user_id`/`api_key_id` from the
  ContextVars. An explicitly-passed param still wins, so background/system jobs
  (brief generation, evaluation) remain system-attributed (NULL).

This is what repairs the existing `user_id` hole without touching any LLM call
site.

### 3. Endpoint

Extend `backend/app/routers/insight.py:usage_summary`:

- Add `"api_key": "api_key_id"` to `_GROUP_FIELDS`.
- Add optional `from`/`to` query params → `created_at__gte` / `created_at__lt`
  in UTC, applied to **all** group-by modes.
- For `group_by=api_key`: after aggregation, fetch the relevant `UserAPIKey`
  rows in one query and enrich each result with `name`, `key_prefix`, and owner
  email. The NULL-key aggregate becomes `key="—"`, `name="web/session"`.

`GET /api/v1/insight/usage?group_by=api_key&from=…&to=…` — admin-only (already
gated by `require_admin`).

### 4. Frontend

- New page `frontend/src/features/usage/UsageAnalyticsPage.tsx` + `usageApi.ts`,
  mirroring the existing audit-log page (React Query + shadcn table).
- Route `/usage` under `<ProtectedRoute requireAdmin>` in `App.tsx`, plus a nav
  link.
- Columns: key name, prefix, owner, prompt tokens, completion tokens, total
  tokens, cost; with from/to date pickers. The catch-all row renders as
  "— (web/session)".

### 5. Testing (TDD)

- Backend:
  - `_record_usage` captures `api_key_id` and `user_id` from the ContextVars.
  - Endpoint groups by api_key correctly and enriches with key metadata.
  - Keyless rows aggregate into the single catch-all bucket.
  - Date filter scopes results correctly (UTC boundaries).
- Frontend: render rows and re-fetch on date-filter change.

## Out of scope

- Per-key drill-down by model/purpose or time series.
- Backfilling attribution onto historical rows (data unavailable).
- Multi-worker rate limiting (tracked separately).
