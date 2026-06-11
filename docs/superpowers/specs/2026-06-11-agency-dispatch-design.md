# Agency Dispatch (API + MCP) — Design + Plan

**Date:** 2026-06-11
**Status:** Approved (autonomous run; user pre-authorized "both, even if speculative")
**Branch:** `feat/agency-dispatch`

## Goal

Replace the two `NotImplementedError` stubs in `app/services/chat/graph.py`
`dispatch_to_agencies` (API and MCP connection types) with real dispatch, so the
chat pipeline can actually query API- and MCP-type agencies, not only A2A.

## Motivation

`dispatch_to_agencies` currently handles only `A2A`; `API` and `MCP` raise
`NotImplementedError` (caught → status `error`). The repo already contains working
references for both protocols:
- **API:** `app/scheduler.py::agency_chat_item` builds requests from `agency.api_headers`
  and `agency.expected_payload`, substituting placeholders (`__query__`,
  `__session_id__`, `__user_id__`, `__conversation_id__`).
- **MCP:** `app/mcp/client.py` uses `fastmcp.Client` — `async with Client(url) as c: await c.call_tool(name, args)`.

## Architecture

Extract dispatch out of `graph.py` into a focused, testable module
`app/services/chat/dispatch.py`. `graph.py::dispatch_to_agencies` becomes a thin
orchestrator that calls `dispatch_one(route, conversation_id)`.

### New file: `app/services/chat/dispatch.py`

Pure helpers (no I/O — fully unit-testable):

- `build_api_payload(expected_payload: dict, sub_question: str, conversation_id: str) -> dict`
  For each key/value in `expected_payload`, substitute by BOTH conventions seen in the repo:
  - sentinel values: `"__query__"` → sub_question; `"__session_id__"`/`"__conversation_id__"` →
    conversation_id (or a fresh uuid if empty); `"__user_id__"` → fresh uuid.
  - key-name fallback (for the `{"query": "...", "session_id": ""}` template style seen in
    real agency data): key `"query"` → sub_question; key `"session_id"`/`"conversation_id"`
    → conversation_id (or fresh uuid); key `"user_id"` → fresh uuid.
  - otherwise keep the original value.
- `build_api_headers(api_headers: list[dict] | None) -> dict`
  Start with `{"content-type": "application/json"}`; add each `{"name", "value"}` lower-cased.
- `select_mcp_tool(tools: list) -> str` **[speculative]**
  Each tool has a `.name` (fastmcp `Tool`) or is a dict with `"name"`. Prefer the first
  tool whose name contains any of `chat`, `ask`, `query`, `question`, `answer` (case-insensitive);
  else the first tool. Raise `ValueError("no MCP tools available")` if the list is empty.
- `build_mcp_args(tool, sub_question: str) -> dict` **[speculative]**
  Read the tool's input schema (`.inputSchema` attr or `["inputSchema"]`/`["input_schema"]` key);
  look at its `properties`. If a property named `query`/`question`/`message`/`text`/`input`
  exists, map sub_question to the first such match. Else if there is exactly one string
  property, use it. Else `{}` (no-arg tool).
- `extract_mcp_text(result) -> str` **[speculative]**
  From a fastmcp `CallToolResult`: prefer `.data` if present; else `.structured_content`;
  else join `.content[*].text`; coerce to a string. Tolerate dicts/objects.

Dispatch functions (I/O — tested with mocks):

- `async dispatch_a2a(route, conversation_id) -> dict` — move current A2A logic verbatim
  (POST `endpoint_url` with `{"session_id": uuid, "query": <prefixed sub_question>}`).
- `async dispatch_api(route, conversation_id) -> dict` — build headers+payload via the helpers,
  POST `route["endpoint_url"]` with `httpx.AsyncClient(timeout=settings.AGENCY_CHAT_TIMEOUT)`;
  200 → `{"agency", "response": resp.json(), "status": "ok"}`; non-200 →
  `{"agency", "response": f"HTTP {code}: {text}", "status": "error"}`.
- `async dispatch_mcp(route, sub_question) -> dict` **[speculative]** — `async with fastmcp.Client(route["endpoint_url"]) as client:` → `list_tools()` → `select_mcp_tool` → `build_mcp_args` → `call_tool` → `extract_mcp_text`. Returns `{"agency", "response": <text>, "status": "ok"}`.
- `async dispatch_one(route, conversation_id) -> dict` — switch on `route["connection_type"]`
  to A2A/API/MCP; unknown → `{"agency", "response": f"Unknown connection_type: {conn}", "status": "error"}`.
  Wrap the whole body in `try/except Exception as e` returning
  `{"agency": route["agency_name"], "response": str(e), "status": "error"}` (preserves current
  error-handling contract, including MCP/API connection failures).

### Modified: `app/services/chat/graph.py`

- `route_query`: also enrich each route with `api_headers` from the agency map
  (currently enriches only `endpoint_url` and `expected_payload`).
- `dispatch_to_agencies`: replace the inner `call_agency` body with a call to
  `dispatch_one(route, state.conversation_id)`; keep the `asyncio.gather` fan-out.
- Remove now-unused inline A2A/httpx code from graph.py (moved to dispatch.py). Keep imports tidy.

## Testing

New `tests/services/test_dispatch.py`, all mocked (no live network/MCP):
- `build_api_payload`: sentinel convention; key-name convention; empty conversation_id → uuid; passthrough of unrelated keys.
- `build_api_headers`: default content-type; merges + lowercases custom headers; None → just default.
- `select_mcp_tool`: picks chat-like tool; falls back to first; empty → raises.
- `build_mcp_args`: maps to query/question property; single-string-property fallback; no-arg tool → {}.
- `extract_mcp_text`: `.data` / `.structured_content` / `.content[*].text` paths.
- `dispatch_api`: 200 → ok with json; non-200 → error with status; payload/headers built correctly (assert the POST call).
- `dispatch_mcp`: mock `fastmcp.Client` async-context-manager; assert tool selected + args + ok result; connection error → caught by `dispatch_one` → status error.
- `dispatch_one`: routes by type; A2A path; unknown type; exception → error dict.

Plus update/extend `tests/services/test_chat_graph.py` so the API/MCP dispatch tests reflect the
new real behavior (the old "not yet implemented" characterization tests must be replaced —
they were explicitly the regression net for THIS change). Keep A2A + unknown + synthesize tests.

## Verification (no live runtime available)

- `cd backend && .venv/bin/python -m pytest tests/ -q` — all green.
- `cd backend && .venv/bin/python -c "from app.main import app"` — imports.
- `gofmt`/golangci-lint: N/A (Python).
- **Cannot** verify against a real API/MCP agency endpoint in this environment — the MCP
  tool-selection/arg-mapping heuristics are speculative and flagged as such in the PR.

## Out of Scope

- Changing the LLM router prompt or synthesis.
- A2A behavior changes (pure move).
- Persisting dispatch ConnectionLogs (the scheduler does that for health checks; the chat
  path historically did not log per-agency dispatch — leave unchanged).
- Frontend, analytics, other services.
