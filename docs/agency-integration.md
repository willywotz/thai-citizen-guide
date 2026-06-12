# Agency Integration Guide

This guide explains how to connect a government agency's backend to the Thai
Citizen Guide gateway. After onboarding, the gateway routes citizen questions
to your endpoint and synthesizes answers from one or more agency responses.

---

## Overview

The gateway receives a citizen's question, decomposes it into sub-questions,
dispatches each sub-question to the relevant agency endpoint, and synthesizes
the responses into a single answer. An agency's job is to expose an endpoint
that accepts a sub-question and returns a relevant answer within the configured
timeout.

---

## Connection types

Each agency record has a `connection_type` field. The gateway's `dispatch_one`
function branches on this value:

| Type  | Protocol                  | When to use |
|-------|---------------------------|-------------|
| `API` | HTTP POST (JSON)          | Your service exposes a REST endpoint that accepts a JSON body and returns JSON. This is the most common integration path. |
| `MCP` | Model Context Protocol (SSE transport) | Your service implements MCP. The gateway connects via `fastmcp.Client`, lists tools, selects the best tool by name heuristic (prefers tools whose name contains `chat`, `ask`, `query`, `question`, or `answer`), and calls it. See `spec/mcp-server.md` for the SSE/POST transport requirements. |
| `A2A` | Agent-to-Agent (HTTP POST) | Your service is an AI agent that accepts a free-form JSON body `{"session_id": "<uuid>", "query": "<question>"}`. The gateway always uses a freshly generated UUID for the session and prepends a Thai instruction requesting that sources be cited. |

---

## The API contract

### Request

The gateway POSTs `application/json` to `endpoint_url`. The body is built from
`expected_payload` by `build_api_payload` in `dispatch.py`.

#### Placeholder substitution

`expected_payload` is a JSON object whose *values* can contain sentinel strings.
The gateway replaces them as follows:

| Value in template         | What the gateway sends |
|---------------------------|------------------------|
| `"__query__"`             | The sub-question text  |
| `"__session_id__"` or `"__conversation_id__"` | The conversation ID, or a generated UUID if none exists |
| `"__user_id__"`           | A freshly generated UUID per request |
| Any other value           | Passed through unchanged |

In addition to value-based substitution, the gateway also handles certain
**key names** implicitly, regardless of what the value says:

| Key name                          | What the gateway sends |
|-----------------------------------|------------------------|
| `query`                           | The sub-question text  |
| `session_id` or `conversation_id` | The conversation ID (or generated UUID) |
| `user_id`                         | A freshly generated UUID per request  |

The value-based sentinel check runs first; the key-name fallback runs only when
the value did not match a sentinel. If both the key name and the value are
significant, the value sentinel takes precedence.

Example `expected_payload`:

```json
{
  "query": "__query__",
  "session_id": "__session_id__"
}
```

Resulting POST body:

```json
{
  "query": "ขอข้อมูลการติดต่อหน่วยงาน",
  "session_id": "b3d2e1a0-..."
}
```

#### Headers

`api_headers` is a list of `{"name": ..., "value": ...}` objects stored on the
agency record. The gateway lower-cases every header name before sending. The
`content-type: application/json` header is always included and cannot be
overridden via `api_headers` (the `api_headers` entry would simply overwrite
the same lower-cased key).

Example:

```json
[{"name": "Authorization", "value": "Bearer my-token"}]
```

The gateway sends: `authorization: Bearer my-token`.

### Response

- **HTTP 200**: the gateway treats the response body as a successful answer and
  passes it to the synthesis step.
- **Any other status code**: the gateway records
  `"HTTP <code>: <body>"` as an error response and the synthesis step receives
  an error signal for this agency.

Your endpoint must return HTTP 200 for every valid question. Returning a 4xx or
5xx causes this agency's contribution to be marked as an error for that request.

### Timeouts

| Setting                  | Default | Scope |
|--------------------------|---------|-------|
| `AGENCY_CHAT_TIMEOUT`    | 180 s   | Per-agency fallback (API and health probes) |
| `dispatch_timeout_s`     | —       | Per-agency override; if set, takes precedence over `AGENCY_CHAT_TIMEOUT` |
| `A2A_DISPATCH_TIMEOUT`   | 30 s    | Fixed timeout for all A2A dispatches |

The timeout logic in `_dispatch_timeout`:

```python
route.get("dispatch_timeout_s") or settings.AGENCY_CHAT_TIMEOUT
```

So a `dispatch_timeout_s` of `0` or `null` falls back to the global default.

### Retries

For both API and A2A dispatches, the gateway wraps the HTTP call in
`retry_async`, which retries up to 3 attempts on transient errors
(`ConnectError`, `ConnectTimeout`, `ReadTimeout`, `RemoteProtocolError`) with
exponential backoff (0.5 s, 1 s). Non-transient errors (e.g., HTTP 4xx/5xx)
are **not** retried.

Because transient failures may cause the same request to be sent more than
once, your endpoint should be safe to receive duplicate POSTs for the same
question (idempotent-friendly).

---

## Health probes

Every **15 minutes** (default `HEALTH_CHECK_INTERVAL_MINUTES = 15`), the
scheduler calls `agency_chat_item` for each non-draft, non-disabled agency.

For `API` agencies, the probe:

1. Builds the same headers as a real dispatch (lower-cased `api_headers` plus
   `content-type: application/json`).
2. Builds a payload from `expected_payload` with the same placeholder
   substitution rules, except `__query__` is replaced with a Thai legal-inquiry
   probe string (e.g., `"ปรึกษากฎหมาย" + <random data_scope entry>`).
3. POSTs to `endpoint_url` with a timeout of `AGENCY_CHAT_TIMEOUT` (180 s
   default).
4. Records the outcome in `ConnectionLog` — HTTP 200 = success, anything else =
   error.

For `MCP` and `A2A` agencies the probe delegates to `test_connection`.

Your endpoint must return **HTTP 200** for probe requests. Probe payloads look
identical to real-user requests. The gateway does not send a special
`X-Health-Probe` header, so you cannot distinguish probes from real traffic.

---

## Conformance battery

Before an agency can be moved from `draft` to `active`, an administrator runs
the conformance battery (`run_conformance` in `conformance.py`). All five checks
must pass.

| Check           | What it tests |
|-----------------|---------------|
| `responds`      | The endpoint returns status `ok` (HTTP 200) for a Thai question within the configured timeout. |
| `non_empty`     | The answer string in the response is non-empty after stripping whitespace. |
| `thai_text`     | The answer contains at least one Thai Unicode character (U+0E00–U+0E7F). |
| `concurrency_3` | Three simultaneous requests all succeed. |
| `garbage_input` | The endpoint does not crash when sent a garbage string (`"\x00\x01 ###"`); any response (including an error answer) is acceptable. |

The conformance report is stored in `agency.conformance_report`. An agency
with a failing report cannot be activated.

---

## Onboarding walkthrough

The following steps use the reference agency in `examples/reference-agency/`.

### 1. Run the reference agency

```bash
cd examples/reference-agency
pip install "fastapi>=0.110.0" "uvicorn[standard]>=0.29.0" "pydantic>=2.0.0"
uvicorn main:app --port 9000
```

Verify it is up:

```bash
curl http://localhost:9000/health
# {"status":"ok"}

curl -X POST http://localhost:9000/chat \
     -H "content-type: application/json" \
     -d '{"query":"ขอข้อมูลการติดต่อหน่วยงาน"}'
# {"answer":"(ตัวอย่าง) ได้รับคำถาม: ขอข้อมูลการติดต่อหน่วยงาน","sources":[...]}
```

### 2. Register the agency in the gateway

Create an agency record via the admin UI or API with:

| Field              | Value |
|--------------------|-------|
| `connection_type`  | `API` |
| `endpoint_url`     | `http://localhost:9000/chat` |
| `expected_payload` | `{"query": "__query__", "session_id": "__session_id__"}` |
| `status`           | `draft` (default) |

Leave `dispatch_timeout_s` empty to use the global default (180 s).

### 3. Run the conformance battery

From the admin interface, trigger "Run conformance" for the agency. The gateway
sends the five checks described above. A passing result looks like:

```json
{
  "passed": true,
  "checks": [
    {"name": "responds",      "passed": true, "detail": "42ms"},
    {"name": "non_empty",     "passed": true, "detail": ""},
    {"name": "thai_text",     "passed": true, "detail": ""},
    {"name": "concurrency_3", "passed": true, "detail": ""},
    {"name": "garbage_input", "passed": true, "detail": "did not crash"}
  ]
}
```

### 4. Activate the agency

Once conformance passes, an administrator sets the agency status to `active`.
The gateway will start routing relevant citizen questions to your endpoint in
the next dispatch cycle.

---

## Reference

- `backend/app/services/chat/dispatch.py` — dispatch logic
- `backend/app/scheduler.py` — health probe scheduler
- `backend/app/services/conformance.py` — conformance battery
- `backend/app/models/agency.py` — agency model fields
- `backend/app/config.py` — default timeout and interval values
- `spec/mcp-server.md` — MCP SSE transport requirements (Thai)
- `examples/reference-agency/main.py` — runnable reference implementation
