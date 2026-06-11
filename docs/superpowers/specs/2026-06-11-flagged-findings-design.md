# Flagged Findings — Follow-up Fixes

**Date:** 2026-06-11
**Status:** Approved (autonomous; user said "go ahead" on the PR #15 flagged items)
**Branch:** `fix/flagged-findings`

Addresses the items flagged (not auto-fixed) in the bug-hunt PR #15, now that usage was
investigated. Each fix is chosen to be **non-breaking by default** or **safe by construction**;
metric/semantic changes are documented for easy review/revert.

## G1 — Password-reset token exposure (`auth.py`) — add a prod kill-switch (non-breaking)
The forgot-password endpoint returns `reset_token` in the JSON response. The frontend
`ForgotPasswordPage.tsx` deliberately reads and displays it (copy button) — it's the intended
no-email reset UX. Removing it would break reset.
**Fix:** add setting `EXPOSE_PASSWORD_RESET_TOKEN: bool = True` (default preserves current
behavior). Only include `reset_token` in the response when the flag is true. Always set
`user.reset_token` server-side regardless. This gives a one-line prod hardening switch with
**zero default behavior change**. Document that production should set it false + add email.

## G2 — `POST /agencies/{id}/increment-calls` unauthenticated — add admin auth
No in-repo caller (the agent-proxy increments `total_calls` via direct DB). Unauthenticated
write to a counter is a real vuln.
**Fix:** add `_: User = Depends(require_admin)` to the endpoint, matching the router's other
mutating endpoints. **Assumption:** the endpoint is not relied on by an unauthenticated
external client. Documented; trivially revertible.

## G3 — `chat.py` `message_count = len(answer)` (6 sites) — count messages, not characters
Stores answer character length in a field that counts messages (see `conversations.py`).
**Fix:** each Q&A turn creates 1 user + 1 assistant message = 2. Replace `len(answer)` with `2`:
on new-conversation create `message_count=2`; on continue `conv.message_count += 2`. Apply to
all of chat_internal, chat_external, and `_save_stream_conversation`. **Assumption:**
`message_count` = number of messages; each turn = 2. (No live DB to migrate historical rows;
this corrects new writes only.)

## G4 — `similarity` v3 cache never hits — set `assistant_message_id` on the v3 log
`chat_external` creates the `ConnectionLog` before the messages and without
`assistant_message_id`, so `ConnectionLog.get(assistant_message_id=...)` in
`find_similar_question` always raises → v3 cache disabled.
**Fix:** reorder `chat_external` so the user+assistant messages are created first, then create
the `ConnectionLog` with `message_id=query_msg.id` and `assistant_message_id=response_msg.id`
(mirroring the v4 `_save_stream_conversation` which already does this). Keep the logged
detail/bodies identical. Existing tests must stay green.

## G5 — `agent-proxy/handler.go` increments `total_calls` on error responses — only on 2xx
`incrementTotalCalls` runs unconditionally, inflating usage with failed calls.
**Fix:** only call `incrementTotalCalls` when the upstream status is 2xx (reuse the existing
`status == "success"` determination). **Assumption:** `total_calls` is a successful-usage
metric (matches dashboard "agency usage"). Documented; revertible.

## G6 — `chat.py` cached-SSE `json.loads(conn_log.response_body)` — guard against bad body (defensive)
In the cached stream path, a None/malformed `response_body` would raise inside the async
generator and abort the SSE stream silently.
**Fix:** wrap in try/except; on failure, fall back to the cached `asst_msg.content` answer
(or emit an error event) rather than crashing the generator. Behavior unchanged on the happy path.

## G7 — `insight.py` slices `dict_values` views — materialize to list (defensive)
Storing `entry["data"].values()` (a live view) and slicing it is CPython-insertion-order
dependent.
**Fix:** wrap in `list(...)` before slicing/storing so ordering is explicit. Behavior-preserving
on CPython; robust elsewhere.

## Verification
- Backend: `cd backend && .venv/bin/python -m pytest tests/ -q` (all green; add a test for the
  G1 flag gating behavior and G2 auth requirement where feasible), `from app.main import app`.
- agent-proxy: `gofmt -l . && go build ./... && go vet ./... && go test ./... && golangci-lint run`.

## Out of scope
- Email infrastructure for password reset (the real long-term G1 fix).
- Historical data migration for message_count.
