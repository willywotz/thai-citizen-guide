# Frontend Bug Hunt — Fixes + Findings

**Date:** 2026-06-11
**Status:** Approved (autonomous; user said "go ahead")
**Branch:** `fix/frontend-bug-hunt`

A frontend bug-hunt swept `frontend/src` (the earlier hunt covered only backend + agent-proxy).
This FIXES the high-confidence, clearly-correct bugs (verified by `tsc` + `vitest` + `eslint`,
since no live runtime) and FLAGS the edge/uncertain ones.

## FIXES

### B1 — `AgencyDetailPage.tsx` crash: `logs.items` used without the null-guard the sibling memo has
The `stats` memo guards `if (!logs) return …`; the `hourlyData` memo accesses `logs.items.forEach`
unguarded → `TypeError` when `logs` is undefined (cold cache before `initialData`).
**Fix:** add the same `if (!logs) return []` guard to `hourlyData`.

### B2 — `useChat.ts` multi-turn break: `handleSend` reads stale `conversationId` state
`handleSend` closes over `conversationId` (state), which lags behind `streamingRef.current.sessionId`.
A fast follow-up send can post without `conversation_id`, silently starting a new thread.
**Fix:** keep a `conversationIdRef` updated whenever `conversationId` changes (and on finalize), and
have `handleSend` read the ref (always current) when building the request. Keep public API unchanged.

### B5 — `ApiKeysPage.tsx`: API keys rendered in plaintext (masking commented out)
`maskKey` is defined but the render uses the raw `k.key`. Credentials visible in the DOM.
**Fix:** display `maskKey(k.key)`. Preserve any copy-to-clipboard using the real key value (copy the
real key, display the masked one). If a per-row reveal toggle is trivial, add it; otherwise masked-only.

### B4 — connection-logs query-key mismatch: invalidation never matches the live query
Live key is `['connection-logs', paramsObject]`; the post-test invalidation uses
`['connection-logs', agencyIdString]` → never matches → logs stay stale until the 30s refetch.
**Fix:** make the two consistent — align the query key and every `invalidateQueries`/`setQueryData`
for connection-logs to the same shape (prefer `['connection-logs', agencyId, ...otherParams]`).
Grep all usages and update together so nothing else breaks.

### B6 — `useChat.ts` `handleRate`: optimistic update never rolled back on failure
`updateMessageRating(...)` is fire-and-forget; if it fails, the UI still shows the rating saved.
**Fix:** await it; on falsy/failed result, roll back the optimistic `setMessages` change (and surface
nothing worse than before). Keep it non-throwing.

### B7 — `useChat.ts`: in-flight SSE not aborted on unmount → state-update-after-unmount + leaked stream
**Fix:** add an unmount cleanup `useEffect(() => () => abortRef.current?.abort(), [])` so navigating
away mid-stream aborts the fetch/SSE.

### B8 + S1 — `useChat.ts` error handling: stale streaming state + swallowed SSE error
On a non-abort error, `streamingState` is not reset (stale pipeline steps leak into the next send),
and an SSE `error` event (sets `done=true`, no `answer`) results in NO chat bubble — the error is
silently swallowed.
**Fix:** in the catch (non-abort) path, reset `setStreamingState(INITIAL_STREAMING_STATE)`. And when
finalizing with an error and no answer, append a visible assistant error message bubble instead of
disappearing silently. (Use the existing `buildGenericErrorMessage`/`buildConnectionLostMessage`
helpers in `chatHelpers.ts`.)

### S2 — `agencyForm.ts`: `parseInt` without radix + NaN passthrough
`parseInt(state.rateLimitRpm)` → base-10 ambiguity and `NaN` for non-numeric input (serialized to the
backend). **Fix:** `parseInt(x, 10)`; if the result is `NaN`, send `null`. Add a unit test in
`agencyForm.test.ts` (non-numeric → null; "0100" → 100; "60" → 60).

## FLAGGED (not fixed — edge/uncertain)

- **B3** — SSE state-updater race can briefly overwrite `cancelStream`'s reset. The existing
  `signal.aborted` guard already prevents the main symptom; a full fix needs a generation counter in
  the streaming updaters. Low value vs. risk without live testing. Recommend: add an abort/generation
  check inside the stream callbacks later.
- **B9** — `AgencyFormDialog` reset effect depends on `[agency, open]`; a rapid edit→close→create
  toggle is render-timing-fragile. Recommend: key the dialog by agency id or reset on explicit open.
- **S3** — `HistoryPage` `new Date(c.date)` breaks the date filter IF the API returns a locale string.
  The implementer should CHECK the actual `HistoryItem.date` format first: if it's already ISO/parseable,
  no change; if it's a Thai-locale display string, the filter needs the raw ISO date from the API.
  Fix only if clearly broken; otherwise flag (don't guess).

## Verification (all must pass; no live runtime)
- `cd frontend && node_modules/.bin/tsc --noEmit` → exit 0
- `cd frontend && node_modules/.bin/vitest run` → all pass (67 baseline + new)
- `cd frontend && node_modules/.bin/eslint <changed files>` → no new errors

## Out of scope
Backend/agent-proxy; visual redesign; the FLAGGED items; new features.
