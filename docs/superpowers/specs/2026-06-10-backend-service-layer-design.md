# Backend Service Layer Refactor

**Date:** 2026-06-10
**Status:** Approved

## Goal

Separate HTTP concerns from business logic across the FastAPI backend. Routers handle request parsing, auth, and response formatting only. Services own LLM calls, external HTTP, analytics queries, and data transforms. No functional changes — improvements allowed (dead code removal, logging cleanup).

## Motivation

- `app/routers/chat.py` is 919 lines mixing LangGraph state, prompt builders, LLM calls, and agency dispatch with HTTP route handlers
- `app/routers/agencies.py` is 666 lines with connection-testing protocol probers embedded inline
- `app/main.py` has a background scheduler inline (240 lines total)
- `app/models.py` duplicates `app/models/user.py`
- Business logic is untestable without spinning up FastAPI and a DB

## Architecture

Two layers with clear responsibilities:

| Layer | Directory | Owns |
|-------|-----------|------|
| HTTP | `app/routers/` | Route decorators, auth deps, request/response validation, HTTP errors |
| Business | `app/services/` | LLM calls, external HTTP, analytics queries, data transforms |

Models, schemas, auth, MCP, and utils are unchanged.

## Module Map

### Chat

**Before:** `app/routers/chat.py` (919 lines — LangGraph graph, nodes, prompt builder, LLM client, agency dispatch, HTTP routes all in one file)

**After:**
- `app/routers/chat.py` (~60 lines) — FastAPI routes, auth, calls graph service, returns response
- `app/services/chat/llm.py` — `call_llm()`, `build_router_prompt()`
- `app/services/chat/graph.py` — `AgentState` dataclass, all four LangGraph nodes (`load_agencies`, `route_query`, `dispatch_to_agencies`, `synthesize`), graph construction and execution entry point

### Agencies

**Before:** `app/routers/agencies.py` (666 lines — CRUD routes plus full protocol probers for REST/MCP/A2A)

**After:**
- `app/routers/agencies.py` (~250 lines) — CRUD routes + test endpoint (thin: calls service, maps result to response model)
- `app/services/agency.py` — `test_connection()`, `_test_rest()`, `_test_mcp()`, `_test_a2a()`, OpenAPI spec-parsing LLM call, response serialization helpers

### Analytics

**Before:** `app/routers/insight.py` (257 lines), `app/routers/executive_summary.py` (126 lines), `app/routers/dashboard.py` (107 lines) — each with DB queries inline in route handlers

**After:**
- All three routers become thin wrappers that call functions in `app/services/analytics.py`
- `app/services/analytics.py` — all Tortoise/raw-SQL analytics queries, grouped by domain (insight, executive summary, dashboard)

### Scheduler

**Before:** `agency_chat_item()`, `agency_chat_test()`, `start_scheduler()`, `stop_scheduler()` inline in `app/main.py`

**After:**
- `app/scheduler.py` — all scheduler logic
- `app/main.py` imports and calls `start_scheduler` / `stop_scheduler` in the lifespan context manager

### Models deduplication

**Before:** `app/models.py` defines `User` — a duplicate of `app/models/user.py`

**After:**
- `app/models.py` deleted
- Any import of `from app.models import User` updated to `from app.models.user import User`
- `app/models/__init__.py` already re-exports model classes; verify it covers all references

## Dead Code Cleanup

Applied during extraction:

- Remove commented-out `LLM = ChatOpenAI(...)` block in `chat.py` (never used)
- Replace `print()` calls in `chat.py` and `main.py` with `logger.debug` / `logger.info` using the existing `logging.getLogger(__name__)` pattern
- API and MCP dispatch stubs in `dispatch_to_agencies` (returning `"[API mock] ..."`) → replaced with `raise NotImplementedError("...")` and a `# TODO` comment so the gap is explicit

## Testing Impact

Service functions are plain async functions — testable with `pytest-asyncio` and mocked `httpx.AsyncClient` without a running FastAPI app or DB. Routers become integration-testable via `TestClient` with simpler setup.

No new tests written in this refactor; the structure makes them writable.

## Out of Scope

- New features
- Changes to `app/schemas/`, `app/auth/`, `app/mcp/`, `app/utils/`
- Migrations or model changes
- `app/routers/messages.py`, `api_key.py`, `connection_logs.py`, `settings.py`, `seed.py` — already thin enough
- `app/routers/auth.py`, `app/routers/conversations.py` — business logic already minimal or delegated to `app/auth/`
