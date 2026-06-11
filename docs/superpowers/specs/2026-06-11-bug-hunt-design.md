# Cross-Component Bug Hunt — Fixes + Findings

**Date:** 2026-06-11
**Status:** Approved (autonomous run; user chose "fix with tests, document assumptions")
**Branch:** `fix/bug-hunt`

A bug-hunt swept `backend/app/` and `agent-proxy/`. This sub-project FIXES the clear,
high-confidence, low-ambiguity bugs (each with a test pinning the corrected behavior and a
documented assumption) and FLAGS the rest (where an auto-fix could break a working flow or
where the "correct" behavior is a product decision).

## FIXES (with tests + assumptions)

### F1 — `analytics.get_agency_health`: error/uptime metric is inverted and mis-scaled
`error_count` uses `SUM(CASE WHEN status >= 'success' ...)` (lexical hack that counts
successes, not errors) and `errorRate` is a 0–1 fraction consumed as a percentage in
`uptime = 100.0 - errorRate` (→ ~100% always).
**Fix:** count failures with `SUM(CASE WHEN status <> 'success' THEN 1 ELSE 0 END)`;
compute `errorRate` as a **percentage** `error_count/total*100`; `uptime = 100 - errorRate`.
**Assumption:** `status == 'success'` is the success marker (consistent with how
`ConnectionLog.status` is written elsewhere: `"success"` on HTTP 200, else `"error"`). This
makes the per-agency `uptime`/`errorRate` consistent with the historical-series SQL (which
already multiplies by 100).

### F2 — `analytics.get_executive_summary`: `now().month - 1` is 0 in January
Invalid Postgres month → wrong/empty `lastMonthQuestions` (and broken MoM growth) every
January.
**Fix:** `prev_month = (now().month - 2) % 12 + 1`.
**Assumption:** The existing month filters are year-agnostic (e.g. "this month" matches that
month across all years) — that broader imprecision is PRE-EXISTING and left unchanged; this
fix only removes the invalid `month == 0`.

### F3 — `analytics.get_agency_health`: `requestsPerMin` floor-divides to 0 for low traffic
`totalDayRequest // (AVG_LATENCY_WINDOW_DAYS * 1440)` → 0 for any agency with fewer than
~1440×N requests.
**Fix:** float division then `round(..., 2)`.
**Assumption:** `requestsPerMin` is intended as an average rate and a fractional value is
acceptable (the field is already a float-friendly metric).

### F4 — `analytics._get_weekly_brief`: stray `print()` instead of logger
**Fix:** add module `logger = logging.getLogger(__name__)`; replace `print(...)` with
`logger.error(...)`. Behavior-preserving (channel only).

### F5 — `similarity.py` docstring: lists `"trigram"` but code checks `"similarity"`
Setting `SIMILARITY_FALLBACK="trigram"` (per the stale docstring) silently matches nothing.
**Fix:** doc-only — change the docstring to `"similarity", "levenshtein", or "both"` to match
the code and the config comment. **Assumption:** `"similarity"` is canonical (code + config
agree). No behavior change.

### F6 — `chat.py::chat_internal`: `<category>` tag extracted but not stripped from `answer`
Unlike the `<references>` block, the `<category>…</category>` tag is left in the stored and
returned `answer`. The synthesizer appends it on every internal response.
**Fix:** extract a small PURE helper (e.g. `parse_answer_metadata(answer) -> (clean, references, category)`)
into `services/chat`, unit-test it, and use it in `chat_internal` so the tag is stripped
(mirroring the references handling). **Assumption:** the tag should not appear in user-facing
or stored answer text.

### F7 — `agent-proxy/handler.go`: `http.DefaultClient` has no timeout
A stalled upstream hangs the goroutine/connection forever.
**Fix:** use an `http.Client{Timeout: ...}` (timeout from a const or existing config) instead
of `http.DefaultClient`. Must pass `go build`, `go test ./...`, `golangci-lint run`.

### F8 — `agent-proxy/handler.go`: OTel span set OK even on upstream error
The span status is `codes.Ok` regardless of upstream HTTP status, hiding failures in traces.
**Fix:** set the span status to error (with the code) when the upstream status is >= 500
(server error). **Assumption:** 4xx are client errors (not proxy faults); >=500 marks the
span as error. Keep the response passthrough unchanged.

## FLAGGED (documented, NOT auto-fixed — risk/ambiguity; recommend follow-up)

- **SECURITY — `auth.py:174` reset_token returned in the forgot-password JSON response.**
  Enables account takeover for any known email. NOT removed here because there is no email
  infrastructure and removing it would break the only working password-reset path. **Recommend:**
  gate behind a debug flag and deliver via email in production.
- **SECURITY — `agencies.py` `POST /{id}/increment-calls` has no auth.** Allows unauthenticated
  counter inflation. NOT changed because it may be intentional for the public portal flow.
  **Recommend:** confirm intent; if not public, add `require_admin` or rate-limit.
- **`chat.py` `message_count = len(answer)`** (6 sites) stores answer character length in a
  field meant to count messages. NOT auto-fixed: spans internal/external/v4 paths and changing
  it alters dashboard/history numbers; the correct increment (per-message vs per-turn) is a
  product decision. **Recommend:** track the real message count (+2 per Q&A turn or via query).
- **`similarity.py` v3 cache never hits.** `chat_external` (v3) creates `ConnectionLog` without
  `assistant_message_id`, so `ConnectionLog.get(assistant_message_id=...)` always raises →
  cache disabled for v3. NOT auto-fixed: requires reordering message/log creation in
  `chat_external`. **Recommend:** set `assistant_message_id` on the v3 log.
- **`agent-proxy/handler.go` increments `total_calls` on error responses.** Ambiguous whether
  `total_calls` = attempts or successes. **Recommend:** confirm metric definition.
- **`chat.py:~301`** cached SSE path `json.loads(conn_log.response_body)` may raise on
  None/malformed body. **Recommend:** guard defensively.
- **`routers/insight.py:~99-102`** stores `dict_values` views and slices them — CPython-order
  dependent. **Recommend:** materialize to `list` before slicing.

## Verification
- Backend: `cd backend && .venv/bin/python -m pytest tests/ -q` (all green incl. new tests),
  `from app.main import app` imports.
- agent-proxy: `cd agent-proxy && gofmt -l . && go build ./... && go test ./... && golangci-lint run`.

## Out of Scope
Frontend bugs (none high-confidence surfaced); the FLAGGED items above; non-bug refactoring.
