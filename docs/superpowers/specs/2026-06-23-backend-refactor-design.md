# Backend Refactor Design

**Date:** 2026-06-23
**Goals:** Correctness (make it *work*), structure/testability (make it *right*), performance (make it *fast*) for `backend/app/` — applied in that Kent Beck order.

## Context

The FastAPI backend (Python 3.12 · Tortoise ORM · LangGraph · httpx · Redis · FastMCP) has already been through a service-layer split (chat logic now lives in `app/services/chat/`). What remains is a layer of *correctness* bugs (silent fire-and-forget failures, conversations always recorded as `success`, unvalidated LLM JSON, fail-open rate limiting, swallowed config errors), a few *oversized* modules (`chat.py`, `agencies.py`, `analytics.py`), and known *hot-path* inefficiencies (per-agency N+1 counts, full agency list in every router prompt, 3-query similarity lookup).

This refactor fixes behavior first, then decomposes, then optimizes — each step backed by characterization tests written *before* the change.

## Current State (measured `wc -l` on 2026-06-23)

| File | Lines | Note |
|------|------:|------|
| `routers/chat.py` | 602 | 3 near-duplicate save paths; `create_task` w/o error handling; always `status="success"` |
| `routers/agencies.py` | 549 | CRUD + golden-questions + eval + test + parse-spec + owners all in one file |
| `services/analytics.py` | 310 | dashboard + agency-health + executive brief in one module; per-agency N+1 |
| `routers/insight.py` | 256 | two bare `except:` (lines 199, 214); heatmap aggregation in router |
| `services/chat/dispatch.py` | 204 | a2a/api/mcp protocol logic, mostly clean |
| `config.py` | 192 | `apply_overrides` swallows unknown keys + parse errors |
| `services/similarity.py` | 189 | vector → 3 follow-up queries (assistant msg, conversation, conn_log) |
| `main.py` | 161 | OTel init inline; fine |
| `mcp/server.py` | 150 | auth middleware + agency serialization; leaky `__user_id__` defaults |
| `scheduler.py` | 150 | two `create_task` w/o error handling; OTel init duplicated |
| `services/chat/graph.py` | 140 | `json.loads` unvalidated (line 45); loads ALL active agencies every call |
| `services/chat/llm.py` | 122 | `build_router_prompt` embeds full agency list |
| `services/agency_health.py` | 84 | SQLite-portable; OK |
| `services/embedding.py` | 48 | cold httpx client per call; no in-process cache |
| `routers/public_status.py` | 25 | 2 count queries **per agency** (N+1) |

Test suite: ~80 test files under `backend/tests/`. Already covered: rate-limit fail-open (`test_fail_open_observability.py`), dispatch (`services/test_dispatch.py`, 625 lines), chat graph (`services/test_chat_graph.py`), public status (`test_public_status.py`, 13 lines — uptime only), circuit breaker, quota. **Not** covered by characterization tests: the three chat save paths' conversation-status/error semantics, `apply_overrides` failure modes, analytics N+1 query shape, similarity query count.

## Behavior Changes (explicit)

Each is a deliberate fix; bugs are NOT preserved.

1. **Conversation status reflects outcome.** Today every save path hardcodes `status="success"` (chat.py:126, 262, 290, 511, 568, 590). New: when the LangGraph pipeline routed to zero agencies, or every dispatch returned `status != "ok"`, the conversation is saved `status="failed"`. The `/external` and `/stream` paths set `failed` when the upstream answer is empty or upstream returned a non-2xx that we still persisted. **Cache impact:** `find_similar_question` already filters `conv.status == "success"` (similarity.py:54), so failed turns stop poisoning the cache — this is the intended correctness win.
2. **Validate LLM router JSON before use.** `route_query` (graph.py:45) does a bare `json.loads(text)`. New: parse defensively; on `JSONDecodeError` or missing `routes` key, treat as "no routes" (→ synthesize the no-agency message and mark conversation `failed`) instead of raising a 500.
3. **Fire-and-forget failures are surfaced, not lost.** `asyncio.create_task(store_embedding(...))` (chat.py:145) and the two `create_task` calls in `scheduler.start_scheduler` (138-139) drop exceptions silently. New: wrap via a `spawn_logged(coro, name)` helper that attaches a done-callback logging any exception (and adding an OTel span event). Background embedding/classification on the `/external` and `/stream` paths already use `BackgroundTasks`; those handlers will be wrapped to log failures too.
4. **Rate limiter degrades, does not fail open.** Today `RedisSlidingWindowLimiter.check` returns `RateLimitResult(True, 0)` on any `RedisError`/`OSError` (rate_limit.py:151-161) — every request passes unlimited. New: on Redis failure, fall through to a **shared in-process `InProcessLimiter`** so a per-worker budget is still enforced; keep the existing fail-open observability (span event + healthy→failing log once) and add a counter metric `rate_limit.degraded_to_inprocess`. This is neither fail-open nor hard fail-closed.
5. **`apply_overrides` reports unknown/invalid keys.** Today unknown keys are skipped and parse exceptions swallowed (config.py:119-125). New: log a warning per unknown key and per failed coercion (keep applying the rest — DB-driven settings must not crash startup), and return a small report `{applied, unknown, invalid}` for the caller/tests.
6. **`except:` → `except Exception:`.** insight.py:199 and 214 catch bare; replaced with `except Exception:` plus a debug log. No control-flow change.
7. **Audit-log write failures propagate context.** `record_audit` failures inside agency mutations are currently swallowed by `flush_similarity_cache`'s own try/except only; audit writes themselves run unguarded — keep them unguarded (a failed audit write should 500, since it is a compliance record), but document this explicitly so it is not "fixed" into a swallow.

## Target Architecture / File Structure

Decompose by responsibility; keep service functions free of HTTP types so they are unit-testable without a TestClient.

```
app/
  concurrency.py              # NEW: spawn_logged(coro, *, name) — done-callback logs exceptions + span event
  config.py                   # apply_overrides returns OverrideReport; logs unknown/invalid
  routers/
    chat.py                   # thin: dispatch to services/chat/turn.py; ~250 lines
    agencies/                 # NEW package (was 549-line module)
      __init__.py             #   router = APIRouter(...); includes the sub-routers below
      crud.py                 #   list/get/create/put/patch/delete/increment
      lifecycle.py            #   status transition, conformance, test-connection
      golden.py               #   golden-questions + eval-results
      owners.py               #   owners, /mine
      spec.py                 #   parse-spec, mcp/discover
    public_status.py          # single grouped query (no N+1)
    insight.py                # except Exception; heatmap aggregation moved to services/heatmap.py
  services/
    chat/
      turn.py                 # NEW: save_turn(...) — the ONE conversation+message+log writer (transaction)
      graph.py                # validate_router_json; load_agencies uses prefilter+cache
      llm.py
      dispatch.py
    analytics/                # NEW package (was 310-line module)
      __init__.py
      dashboard.py            #   get_dashboard_stats
      health.py               #   get_agency_health (grouped query)
      brief.py                #   executive brief generate/latest/metrics
    heatmap.py                # NEW: usage-heatmap aggregation (moved out of insight router)
    agency_directory.py       # NEW: cached active-agency snapshot for router prompts
    rate_limit.py             # degrade-to-inprocess
    embedding.py              # shared httpx client + small TTL cache
```

Backwards-compatible re-exports: `app/services/analytics.py` becomes a shim re-exporting from `services/analytics/` so existing `from app.services.analytics import get_agency_health` imports (insight.py, scheduler.py) keep working during the transition.

### Dependency injection / mockability

`save_turn`, `dispatch_one`, `call_llm`, `generate_embedding` are already plain async functions — no DI framework needed (matches the agent-proxy YAGNI precedent). The one change: `build_graph()` accepts an optional `agency_loader` callable (defaults to the cached directory) so tests inject a fixed agency list instead of patching `Agency.filter`.

## "Work / Right / Fast" Breakdown

### WORK (correctness — Behavior Changes above)

- Single transactional `save_turn` replacing 3 copy-pasted save blocks in chat.py — wrap `Conversation` + `Message` creation in `in_transaction()` so a mid-write failure can't leave a conversation with the wrong `message_count` or an orphaned user message.
- Conversation `status` derived from routing/dispatch outcome (BC #1).
- Validate router JSON (BC #2).
- `spawn_logged` for fire-and-forget (BC #3).
- Rate limiter degrade (BC #4).
- `apply_overrides` reporting (BC #5).
- `except Exception` (BC #6).
- Health-check semaphore: `agency_chat_item` holds `sem` but the httpx call already has `timeout=AGENCY_CHAT_TIMEOUT` (180s) — add a hard `asyncio.wait_for(..., AGENCY_CHAT_TIMEOUT + 5)` around the whole item so a hung MCP/A2A `Client` context (no inner timeout) can't pin a semaphore slot forever.

### RIGHT (structure)

- Split `agencies.py` → `routers/agencies/` package (5 sub-routers, same paths).
- Split `analytics.py` → `services/analytics/` package + compat shim.
- Move heatmap aggregation out of `insight.py` into `services/heatmap.py`.
- Extract `save_turn` to `services/chat/turn.py`; chat.py becomes thin HTTP/SSE adapter.
- `build_graph(agency_loader=...)` for injectability.
- MCP auth context: document and tighten the `__user_id__`/`__conversation_id__` defaulting in `mcp/server.py:_fetch_agencies` — generate the fallback id ONCE per request (not once per payload key) so the same conversation/user id is used consistently within a response.

### FAST (performance)

- **public_status N+1 → 1 query.** Replace the per-agency `count()` loop with one grouped SQL aggregate (`GROUP BY agency_id` with `FILTER (WHERE status='success')`), joined to the non-draft agency list. ~`2N+1` queries → `2` (agency list + grouped log counts).
- **analytics.get_agency_health N+1 → grouped.** Today 4 aggregate queries *per agency* (current latency, 7d latency, error rate, day count) — replace with one grouped query per metric window keyed by `agency_id`.
- **Router prompt prefilter + cache.** `build_router_prompt` embeds every active agency on every chat. Add `agency_directory.snapshot()` — an in-process TTL cache (invalidated on agency create/update/delete/status-change, the same hooks that already call `flush_similarity_cache`) so `load_agencies` doesn't hit the DB per request, and cap/prefilter obviously-irrelevant agencies by `data_scope` keyword overlap before prompt construction (LLM still does final selection).
- **Similarity 3-query tail → 1 join.** After the vector/text match, similarity.py issues 3 more sequential queries (assistant message, conversation, conn_log). Fold into a single SQL join returning the matched user message + its assistant answer + conn_log + conversation status in one round trip.
- **Embedding client reuse + cache.** `generate_embedding` opens a fresh `httpx.AsyncClient` per call; use a module-level client and a small LRU/TTL cache keyed on `(model, dims, text)` to cut cold-start latency and dedupe identical in-window queries.
- **DB indexes.** Add migration indexes: `connection_log(agency_id, created_at)` (drives public_status + agency_health windows), `messages(role, created_at)` (dashboard/heatmap), and confirm the existing `idx_messages_embedding_cosine` HNSW dimension matches `EMBEDDING_DIMENSIONS=384` (similarity.py already notes the `::vector(384)` requirement).
- **Connection pool sizing.** Make Tortoise pool min/max size configurable (`DB_POOL_MIN`, `DB_POOL_MAX`) in `config.py`/`TORTOISE_ORM` rather than the driver default, sized for `uvicorn --workers 4`.
- **Server-side filter/paginate for list endpoints.** `GET /conversations` returns the *entire* matching list and `HistoryPage` (frontend) date-filters + paginates client-side; push `date_from`/`date_to`/`page`/`page_size` into the ORM query. `GET /connection-logs` gains `status` + `connection_type` ORM filters (it already pages by `agency_id`/`page`/`limit`). All additive — omitting them preserves current behavior. Unblocks the `2026-06-23-frontend-refactor` FAST tier; see API / Migration Notes for the exact param contract.

## API / Migration Notes

Breaking changes are allowed but must be additive where possible. Net public `/api/v1` surface is unchanged in shape:

- **No path changes.** All agency endpoints keep their exact paths after the package split (FastAPI router-include preserves them). Verified registration order constraint (`/mcp/discover`, `/mine`, `/{agency_id}/owners` before `/{agency_id}`) is carried into the sub-routers.
- **Additive field:** chat responses gain nothing new in shape; `conversation_id` semantics unchanged. The only observable change is `Conversation.status` now possibly `"failed"` — this field is internal (not in the chat response body) but IS exposed via `GET /conversations`. Migration note: clients listing conversations may now see `status: "failed"`; document in the changelog. No DB schema change (the column already allows `success|failed`).
- **Rate-limit headers unchanged** (`Retry-After` still returned on 429). Behavior change is internal (degrade vs fail-open).
- **New config keys** (`DB_POOL_MIN`, `DB_POOL_MAX`, embedding-cache TTL) are additive with safe defaults; absent → current behavior preserved.
- **DB migration** (aerich) adds two indexes; forward-only, no data change. Rollback = drop indexes.

### Additive query params — server-side filter/paginate (FAST tier; unblocks `2026-06-23-frontend-refactor`)

The frontend FAST tier ("Server-side filter/paginate", `HistoryPage`) currently fetches the whole conversation list and slices/date-filters client-side. These params push that work into the Tortoise ORM query. **All additive and backward-compatible: omitting every param reproduces today's exact behavior** (full unfiltered list for conversations; the existing `agency_id`/`page`/`limit` paging for connection-logs).

- **`GET /api/v1/conversations`** (`list_conversations`, `conversations.py`). Today accepts only `search` + `filterAgency` and returns the *entire* matching list (no LIMIT). Add:
  - `date_from`, `date_to` — `YYYY-MM-DD` strings, inclusive, filtered on `Conversation.created_at` (`created_at__gte` / `created_at__lt` next-day) in the ORM query, not in Python.
  - `page` (default 1), `page_size` (default current behavior = no limit; when supplied, `offset`/`limit` in the query). Both omitted → unpaginated list as today.
  - Response shape unchanged: `HistoryResponse{success, data, total, response_time}`. `total` already exists; it now reflects the **full filtered count** (`await qs.count()` before slicing), so paged clients get the real total, not the page length. This is the one observable refinement and matches the FE's documented `total` need.

- **`GET /api/v1/connection-logs`** (`list_connection_logs`, `connection_logs.py`). Already paginates (`page`, `limit`) and filters by `search` + `agency_id`. Add:
  - `status` — exact match on `ConnectionLog.status` (`success` | `error`).
  - `connection_type` — exact match on `ConnectionLog.connection_type` (`MCP` | `API` | `A2A`).
  - Accept `page_size` as an alias for the existing `limit` query param so the FE's param name resolves without a separate contract. Response already returns `page_size`/`total_items`; the role-scoping (agency_owner vs admin/auditor) and stats block are unchanged. All new filters apply to both the page query and the count/stats aggregates so totals stay consistent.

Param-name reconciliation vs. the FE spec: `connection-logs` already owns `agency_id` (no work needed there) and its pagination param is `limit`, exposed to the FE as `page_size` via an alias. Conversations gains all four params (`date_from`, `date_to`, `page`, `page_size`). Filtering is pushed into the ORM query — no fetch-all-then-filter.

Versioning: the API stays `v1`. The conversation-status behavior change is recorded in `CHANGELOG`/PR body, not a new API version, since the response contract is unchanged.

## Testing Strategy (characterization-first)

For every module touched, the plan writes **characterization tests pinning current observable behavior first, runs them green against unchanged code, then refactors and keeps them green.** TDD (red→green→refactor) is used only for genuinely *new* behavior (the BC items). Concretely:

- **Before** splitting `chat.py`: characterize `/chat/internal`, `/chat/external`, `/chat/stream` save paths — message counts, `parent_id` linkage, conn-log creation, and *current* `status="success"` (then a separate RED test asserts the NEW `failed` behavior per BC #1).
- **Before** touching `apply_overrides`: characterize that valid keys apply and (current) unknown keys are silently skipped; then RED test for the new warning/report.
- **Before** rate-limit degrade: the existing `test_fail_open_observability.py` pins current fail-open; add a RED test asserting degrade-to-inprocess enforces a limit during outage, then change behavior.
- **Before** perf changes (public_status, agency_health, similarity, embedding): characterize the *result values* (uptime %, latency, match identity) so the query-count optimization is provably output-preserving; add query-count assertions (via a capturing connection wrapper) to prove the N+1 reduction.
- All tests run under the in-memory SQLite `db` fixture where portable; Postgres-only paths (grouped `FILTER`, `::vector`) are guarded/skipped under SQLite and exercised in the Postgres CI job.
