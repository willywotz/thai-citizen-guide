# DB-managed LLM providers & routes — design

**Date:** 2026-07-04
**Status:** Draft (design), pending spec review
**Branch:** `feat/llm-provider-management`

## Goal

Centralize all chat-completions LLM access behind one client where **call sites specify only a `purpose`**. Which provider + model serves each purpose, and every provider's connection/rate-limit config, is **managed at runtime** through admin CRUD backed by DB tables — no code change to remap. Add per-provider **rate limiting with a bounded queue**.

## Scope

- **In:** OpenRouter and ThaiLLM (both OpenAI-style `/chat/completions`). Callers: classification, weekly brief, evaluation (judge), API-spec parsing.
- **Out:** OneChat v3/v4 (external RAG/agent chat engine, SSE) stays as-is. Embedding stack was already removed.

## Non-goals

- No change to OneChat, chat endpoints' request flow, or quota gating.
- Not building a general plugin system — providers are OpenAI-compatible chat-completions endpoints differing only in auth header + whether they report usage.

## Data model (`app/services` + `app/models/`)

### `LlmProvider` (`models/llm_provider.py`, table `llm_providers`)
| field | type | notes |
|---|---|---|
| `id` | UUID pk | |
| `name` | str, unique | slug, e.g. `openrouter`, `thaillm` |
| `base_url` | str | full `/chat/completions` URL |
| `api_key` | str | secret; masked in API responses |
| `auth_header` | str | e.g. `Authorization` or `apikey` |
| `auth_scheme` | str | prefix before key, e.g. `Bearer` or `""` |
| `timeout_seconds` | float | HTTP timeout |
| `request_usage` | bool | inject `usage:{include:true}` (OpenRouter yes, ThaiLLM no) |
| `rate_limit_rps` | int, null | requests/sec; null/0 = unlimited |
| `rate_limit_rpm` | int, null | requests/min; null/0 = unlimited |
| `max_queue_size` | int, default 50 | admission bound; 0 = fail-fast on saturation |
| `enabled` | bool, default true | |
| `created_at`/`updated_at` | datetime | |

### `LlmRoute` (`models/llm_route.py`, table `llm_routes`)
| field | type | notes |
|---|---|---|
| `id` | UUID pk | |
| `purpose` | str, unique | e.g. `classification`, `brief`, `judge`, `parse_spec` |
| `provider` | FK → `LlmProvider` | |
| `model` | str | model id passed to the provider |
| `timeout_override` | float, null | overrides provider `timeout_seconds` when set |
| `enabled` | bool, default true | |
| `created_at`/`updated_at` | datetime | |

Both exported from `models/__init__.py`; one aerich migration creates both tables. Deleting a provider referenced by a route → **409 RESTRICT**.

## Seeding (idempotent, at startup)

In `init_db` (or a seed function it calls), `get_or_create` seeds the two providers from existing env settings (`OPENROUTER_API_URL`/`OPENROUTER_API_KEY`/`LLM_CALL_TIMEOUT`; `PARSE_SPEC_URL`/`PARSE_SPEC_API_KEY`/`PARSE_SPEC_TIMEOUT`) and the four routes (`classification`/`brief`/`judge`→openrouter with `CLASSIFICATION_MODEL`; `parse_spec`→thaillm with `PARSE_SPEC_LLM_MODEL`). Preserves current behavior on fresh and existing DBs. Seed only inserts missing rows (never overwrites admin edits). The old LLM env settings become **seed inputs only** and are removed from `SETTINGS_GROUPS` so the tables are the single source of truth. `rate_limit_*` seed as null (unlimited) unless a known provider default applies.

## Centralized client (`app/services/llm_client.py`)

### Public API
```python
KNOWN_PURPOSES = ("classification", "brief", "judge", "parse_spec")

@dataclass
class LlmUsageInfo:
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None

@dataclass
class LlmResult:
    content: str
    tool_calls: list | None
    usage: LlmUsageInfo
    raw: dict

class LlmError(Exception):
    def __init__(self, message: str, *, status: int | None = None,
                 provider: str | None = None, kind: str | None = None): ...

async def chat(*, purpose: str, messages: list[dict],
               tools: list | None = None, tool_choice=None,
               user_id=None, agency_id=None, conversation_id=None) -> LlmResult
```

### `chat()` flow
1. **Resolve** the enabled `LlmRoute` for `purpose` and its `LlmProvider` from the DB, via a short in-process TTL cache (e.g. 30–60 s) that is **invalidated on any provider/route CRUD write** (`invalidate()` called by the routers). Missing/disabled route or disabled provider → `LlmError(kind="config")`.
2. **Throttle** — `await _acquire(provider)` (see below). Queue-full → `LlmError(kind="queue_full")`.
3. **Build request** — headers `{auth_header: f"{auth_scheme} {api_key}".strip()}`, URL `base_url`, timeout `route.timeout_override or provider.timeout_seconds`. If `provider.request_usage`, add `usage:{include:true}`. Body: `{model: route.model, messages, tools?, tool_choice?}`.
4. **POST** via httpx. Non-2xx or network error → `LlmError(status=…, kind="http"/"network")`.
5. **Parse** → `choices[0].message.content` and `.tool_calls` into `LlmResult`.
6. **Record usage** — write an `LlmUsage` row for **every** provider (purpose-tagged, `cost_usd` may be `None`), reusing the existing `usage_context` for user/api_key id. Recording is wrapped in try/except — accounting never breaks the call.

### Rate-limit queue (`_acquire`)
- **Rate budget** reuses the existing `RateLimiter` (`app/services/rate_limit.py`: Redis sliding-window when configured → shared across workers; in-process fallback with fail-open). Two windows per provider:
  - key `llm:prov:{name}:s`, `limit=rate_limit_rps`, `window_s=1`
  - key `llm:prov:{name}:m`, `limit=rate_limit_rpm`, `window_s=60`
- **Admission control** is a per-worker waiter counter per provider. On entry: if current waiters ≥ `max_queue_size` → raise `LlmError(kind="queue_full")` immediately (no long wait). Otherwise increment, loop: try to acquire both windows; if either denies, `await asyncio.sleep(retry_after)` and retry; decrement on exit (finally). Max wait is naturally bounded by `max_queue_size / rate_limit_rps`.
- **Two-window correctness:** `check()` consumes a slot on success, so acquire must **peek-then-commit** (or order so a partial pass never over-admits). Correctness rule: **never exceed a configured limit**; brief under-utilization under contention is acceptable. `null`/`0` limit = unlimited (limiter returns allowed immediately).

## Backend CRUD API (admin-gated; mirrors `routers/agencies/`)

- `GET/POST /api/v1/llm/providers`, `GET/PATCH/DELETE /api/v1/llm/providers/{id}`
- `GET/POST /api/v1/llm/routes`, `GET/PATCH/DELETE /api/v1/llm/routes/{id}`
- `GET /api/v1/llm/purposes` → `KNOWN_PURPOSES` (populates the route form)
- All mutating endpoints `Depends(require_admin)`; reads allow `require_admin_or_auditor`.
- **Secret masking** (per `routers/settings.py`): `api_key` returned as `MASK` in list/get; on update, if incoming `api_key == MASK`, skip overwriting.
- **Validation:** route `purpose` unique; route `provider` must exist; provider `name` unique; provider delete blocked (409) if a route references it.
- **Audit:** `record_audit(user, "llm_provider.create|update|delete" / "llm_route.*", object_type=…, object_id=…)`.
- **Cache:** every mutation calls the client's `invalidate()`.
- Schemas in `schemas/llm_provider.py` and `schemas/llm_route.py` (Base/Create/Update/Response, list `{data,total}`).
- Routers registered in `app/main.py` with prefix `/api/v1` (literal paths before parametric, per the `agencies/` pattern).

## Caller migration (purpose-only)

- `app/services/chat/llm.py::classify_message_category` → `chat(purpose="classification", messages=[…], user_id/agency_id/conversation_id as today)`, use `res.content`; tolerate `LlmError`.
- `app/services/analytics/brief.py` → `chat(purpose="brief", messages=[…])`; tolerate `LlmError`.
- `app/services/evaluation.py` → `chat(purpose="judge", messages=[…])`.
- `app/services/agency.py::parse_spec` → `chat(purpose="parse_spec", messages=[…], tools=[…], tool_choice=…)`; read `res.tool_calls[0].function.arguments`; failures surface as `LlmError` (was `raise_for_status`/`ValueError`).
- Remove `openrouter_chat` and the inline httpx block in `parse_spec`.

## Frontend (React 18 + Vite + React Query + axios; mirrors `features/api-keys/`)

- `features/llm-providers/` — `LlmProvidersPage` + `llmProviderApi.ts` + List/Create/Edit/Delete dialogs. Form: name, base_url, api_key (masked; blank/mask = unchanged), auth_header, auth_scheme, timeout_seconds, request_usage, rate_limit_rps, rate_limit_rpm, max_queue_size, enabled.
- `features/llm-routes/` — `LlmRoutesPage` + dialogs. Form: purpose (select from `/llm/purposes`), provider (select from providers), model, timeout_override, enabled.
- API via `@/shared/lib/apiClient`. `useQuery` for lists, `useMutation` per action with `invalidateQueries` + toasts. Create/edit hidden for read-only roles (`useAuth().isReadOnly`).
- Register: lazy routes in `App.tsx` under admin `ProtectedRoute`; `ROUTE_ROLES` entries (`/llm-providers`, `/llm-routes` → `["admin"]`) in `features/auth/roles.ts`; nav items in `shared/components/layout/AppSidebar.tsx`.

## Testing

**Backend**
- Models + migration; `models/__init__` exports.
- Seed idempotency (fresh DB seeds; re-run does not overwrite edits; preserves current model/provider defaults).
- CRUD: admin gate (403 for non-admin), secret masking on read + skip-on-mask update, purpose uniqueness (409), provider-in-use delete (409), audit rows written.
- `chat()` resolution: route→provider mapping; missing/disabled route → `LlmError(config)`; auth-header/scheme per provider; `request_usage` injection; `LlmResult` parse (content + tool_calls); `LlmUsage` recorded for both providers; usage-record failure non-fatal; cache invalidation after a write.
- Rate queue: waits when a window is saturated then proceeds; both rps+rpm enforced; `null` = unlimited; queue full (waiters ≥ `max_queue_size`) → `LlmError(queue_full)`; no over-admission across the two windows.
- 4 migrated callers behave as before against a seeded route.

**Frontend**
- api modules call the right endpoints; pages render list + create/edit/delete happy paths (per existing frontend test conventions); provider/route selects populate from `/llm/purposes` + providers list.

## Acceptance criteria

- All 4 call sites pass only a `purpose`; no provider/model/url/key literals remain at call sites; `openrouter_chat` and inline `parse_spec` httpx removed.
- An admin can, at runtime via the UI, add/edit providers (incl. rate limits + queue size) and remap any purpose to a different provider/model, effective without redeploy (cache invalidation).
- With no admin edits, behavior is identical to today (seeded from env).
- Every LLM call records an `LlmUsage` row and respects the provider's rate limits, failing fast when the queue is full.
- `pg_trgm`-style: full backend suite green; migration up/down valid.

## Open implementation notes (for the plan)

- Peek-then-commit for the two-window acquire (avoid partial over-admission).
- Whether `api_key` is stored plaintext (consistent with the settings secret store) or encrypted at rest — default plaintext to match existing pattern; flag if encryption is desired.
- Cache TTL value and the exact `invalidate()` wiring from the routers.
- Seed placement: `init_db` vs a dedicated `seed_llm_defaults()` called at startup after migrations.
