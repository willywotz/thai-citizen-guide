# Backend Service-Layer Test Coverage

**Date:** 2026-06-11
**Status:** Approved
**Branch:** `refactor/backend-service-layer`
**Predecessor:** `2026-06-10-backend-service-layer-design.md` (structural refactor — complete)

## Goal

Raise unit-test coverage on the `app/services/` layer extracted by the preceding
refactor. The refactor moved business logic out of routers into plain async service
functions specifically so they could be tested without a running FastAPI app or DB.
This spec delivers those tests.

## Context

The structural refactor (Tasks 1–6 of the predecessor plan) is committed and the suite
is green (12 tests). Coverage is uneven:

| Service | Lines | Existing tests |
|---|---|---|
| `services/agency.py` | 339 | `test_agency.py` |
| `services/chat/llm.py` | 108 | `test_chat_llm.py` |
| `services/session.py` | 57 | `test_session.py` |
| `services/chat/graph.py` | 161 | **none** |
| `services/similarity.py` | 185 | **none** |
| `services/analytics.py` | 272 | **none** |
| `services/embedding.py` | 48 | **none** |

This spec covers the four untested services (~666 lines).

## Approach

Pure unit tests with `pytest-asyncio`. External dependencies are mocked with
`unittest.mock.AsyncMock` / `patch`, matching the established style in
`test_chat_llm.py` and `test_agency.py`:

- `httpx.AsyncClient` → patched
- `call_llm` (in graph tests) → patched
- Tortoise ORM model calls (`Agency.filter`, `Message.get`, …) and raw
  `conn.execute_query_dict` → `AsyncMock`

**No live database.** Real-DB integration tests are explicitly deferred to a separate
future sub-project (per design decision). This keeps the work bounded and fast.

These are **characterization tests**: they assert the *current* behavior of existing
code. Where reading the code surfaced a genuine bug, the bug is documented below and
left for the future bug-hunt sub-project; the test pins current behavior with a
`# NOTE: characterizes current (buggy) behavior` comment so the future fix is visible.

## Test Modules

### 1. `tests/services/test_chat_graph.py` — highest priority

Core multi-agent pipeline; mostly pure branching, mocks cleanly.

- `should_dispatch`: routes present → `"dispatch"`; empty → `"synthesize"`
- `route_query`: strips `<think>…</think>`; strips ```` ``` ```` code fences; parses JSON
  into `routes`; enriches each route's `endpoint_url` / `expected_payload` from the
  agency map (mock `call_llm`)
- `dispatch_to_agencies`:
  - A2A → posts to endpoint, returns `status: "ok"` (mock `httpx`)
  - **API → `status: "error"`, message "not yet implemented"** (pins TODO behavior)
  - **MCP → `status: "error"`, message "not yet implemented"** (pins TODO behavior)
  - unknown `connection_type` → `status: "error"`
- `synthesize`: empty results → Thai "ไม่พบหน่วยงาน…" message; non-empty → calls
  `call_llm`, returns trimmed `final_answer`
- `build_graph`: compiles without error (smoke)

The API/MCP dispatch tests double as the **regression safety net** for sub-project #2,
which will replace those `NotImplementedError` stubs with real dispatch.

### 2. `tests/services/test_similarity.py`

Cache-hit correctness (a prior `multi-turn-cache-bypass` plan exists — this area has
had bugs).

- `find_similar_question`:
  - embedding provided → `_vector_search` path taken
  - embedding `None` → `_text_fallback_search` path taken
  - each early-return → `None`: no match; no assistant message; conversation not
    `"success"`; missing `ConnectionLog`
  - happy path → `(user_msg, assistant_msg, conn_log)` tuple
- `_text_fallback_search`: config dispatch for `SIMILARITY_FALLBACK` ∈
  `"similarity"` / `"levenshtein"` / `"both"`
- `_levenshtein_search`: `max_distance` computation (`max(1, int(len(query)*(1-thr)))`);
  extension-missing exception → `None`

### 3. `tests/services/test_embedding.py` — quick wins

- `generate_embedding`: no `EMBEDDING_API_KEY` → `None`; HTTP 200 → embedding vector;
  non-200 → retries 3× → `None`; `TimeoutException`/`ConnectError` → retries → `None`
- `encode_embedding` / `decode_embedding`: JSON round-trip

### 4. `tests/services/test_analytics.py` — lightest

Heavy raw-SQL / ORM aggregation; brittle under mocks, so shallow by design.

- Mock `in_transaction` (async context manager) + `execute_query_dict` + ORM
  aggregation chains
- `get_dashboard_stats`: assert returned dict has keys `stats`, `agencyUsage`,
  `weeklyTrend`, `categoryData`; `weeklyTrend` has 7 entries (day names)
- `get_agency_health` / `get_executive_summary`: smoke-test that they assemble the
  expected Pydantic response objects given mocked query results

## Bugs Surfaced (out of scope — documented for bug-hunt sub-project)

1. `analytics.get_agency_health` (~line 108): `error_count` sums
   `status >= 'success'`, which counts **successes**, not errors; the resulting
   `errorRate` is a 0–1 fraction but is consumed as a percentage in
   `uptime = 100.0 - errorRate`. Both the metric and the unit look wrong.
2. `analytics.get_executive_summary` (~line 198): `created_at__month=now().month - 1`
   yields `0` in January (invalid month); month/year boundary math is naive.
3. `analytics._get_weekly_brief` (~line 184): uses `print()` instead of the module
   logger (the refactor was meant to remove `print`).

Tests will characterize current behavior, not assert the fixed behavior.

## Testing / Verification

- Run via the backend venv: `.venv/bin/python -m pytest tests/ -q`
  (the `rtk` hook can't find `pytest` on PATH; the venv interpreter is required)
- All existing 12 tests must stay green
- `gofmt`/`golangci-lint` not applicable (Python only)

## Out of Scope

- Real-DB integration tests (deferred)
- Implementing the agency-dispatch TODOs (sub-project #2)
- Fixing the surfaced analytics bugs (sub-project #4)
- Router, frontend, or agent-proxy tests
- Any change to non-test production code, except possibly a trivial bug-flag comment
