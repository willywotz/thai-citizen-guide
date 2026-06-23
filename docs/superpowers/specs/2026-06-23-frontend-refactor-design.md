# Frontend Refactor Design

**Date:** 2026-06-23
**Goals:** Correct failure behaviour (work), reduce duplication and god components (right), and cut wasted network/render work (fast) across `frontend/src`, without regressing existing tests.

## Context

`frontend/` is a Vite + React 18 + TypeScript SPA (TanStack Query v5, React Router v6, Tailwind, shadcn/ui). It is already organised by feature under `src/features/*` with a shared layer under `src/shared/*`, and most earlier bug-hunt fixes (B6/B7/B8 in `useChat`) are already in place. So this is a *consolidation* pass, not a rewrite: a handful of pages still swallow fetch errors, the SSE reader can hang forever, query config and status labels are copy-pasted, three pages reimplement the same filter+paginate block, and there is **zero** route code-splitting or memoization.

A second, blocking gap: the frontend Vitest suite (30 test files, MSW-backed) is **not run in CI**. `.github/workflows/test.yml` `frontend` job runs only `pnpm exec tsc --noEmit`. Refactors here are risky precisely because the safety net is not enforced.

Cross-cutting decisions (already made): the backend public `/api` may change where clearly better. Server-side filtering/pagination needed for the FAST tier is owned by the backend spec `2026-06-23-backend-refactor`; this spec designs the FE to *consume* those params and references them, it does not redesign endpoints.

## Current State (measured, `wc -l`, non-`ui/` source)

| File | Lines | Notes |
|---|---:|---|
| `features/api-keys/ApiKeysPage.tsx` | 370 | 4 dialogs + list inline; `isLoading` only, no `isError` |
| `features/history/HistoryPage.tsx` | 297 | client-side date filter + client-side paginate full dataset; magic `PAGE_SIZE=10`; dead `allAgencies` array |
| `features/dashboard/DashboardPage.tsx` | 258 | decomposed into 3 subcomponents already; **no `isError`** on 6 polled queries |
| `features/settings/SettingsPage.tsx` | 238 | has `isError` Alert; inline `FieldInput` (lines 22-90) |
| `features/agencies/useAgencies.ts` | 219 | 11 hooks, single-responsibility — healthy, leave |
| `features/heatmap/HeatmapPage.tsx` | 218 | `if (isLoading \|\| !data)` → skeleton **forever** on error |
| `features/chat/useChat.ts` | 208 | streaming + message state mixed in one hook |
| `features/feedback/FeedbackPage.tsx` | 200 | treats fetch failure as "no data" |
| `features/agencies/wizard/AgencyWizardPage.tsx` | 197 | imperative string validation, no zod, no URL/header checks |
| `features/health/HealthPage.tsx` | 193 | `if (isLoading \|\| !data)` → skeleton **forever** on error |
| `features/chat/chatApi.ts` | 161 | SSE `reader.read()` loop has **no timeout** |

Other measured facts:
- `React.lazy` / `Suspense`: **0 occurrences**. `React.memo`: **0 occurrences**.
- `refetchInterval` literals: `health` 15_000, `connection-logs` 30_000 (x2), `agencies` 60_000, `status` 60_000, `executive` 5*60*1000, `dashboard` `REFETCH_INTERVAL=30_000` (named, good); plus `useRealtimeActivity` `POLL_INTERVAL_MS=5_000`.
- `PAGE_SIZE` declared independently in 3 files: history 10, connection-logs 20, audit 50.
- Status-label maps duplicated across `agencies/lifecycle.ts` (canonical), `api-keys/ApiKeysPage.tsx`, `health/HealthPage.tsx`, `status/StatusPage.tsx`.
- Pages **with** error UI already: `executive`, `audit`, `usage`, `settings`, `status`, `my-agencies`. Pages **missing** it: `health`, `heatmap`, `dashboard`, `feedback`, `connection-logs`.

## Target Architecture / File Structure

Keep the feature-folder layout. Add a thin shared layer; do **not** introduce a global store or new data-fetching abstraction.

```
src/shared/
  constants/
    query.ts          // REFETCH, STALE_TIME, PAGE_SIZE (named tiers)
    status.ts         // canonical status label/colour maps (re-export lifecycle.ts)
  hooks/
    usePaginatedFilter.ts   // generic search+filter+paginate for client lists
  components/
    QueryStateBoundary.tsx  // <{isLoading,isError,isEmpty,onRetry}> wrapper
    FieldInput.tsx          // extracted from SettingsPage
    ChartTooltip.tsx        // extracted dup tooltip (dashboard + LiveActivityChart)
features/chat/
  useChatStream.ts     // SSE lifecycle + streamingState (split from useChat)
  useChat.ts           // message list, input, ratings; consumes useChatStream
features/api-keys/
  ApiKeyList.tsx, CreateApiKeyDialog.tsx, EditApiKeyDialog.tsx,
  RevealKeyDialog.tsx, DeleteApiKeyDialog.tsx   // split out of ApiKeysPage
features/agencies/
  agencySchema.ts      // zod schema reused by wizard + detail edit tabs
```

### work — fix wrong/absent behaviour

1. **Error/loading collapse → distinct error state.** `HealthPage` and `HeatmapPage` use `if (isLoading || !data) return <Skeleton/>`. On a failed fetch `data` stays `undefined`, so the skeleton renders forever. Destructure `isError`/`refetch` and route all five gap pages through `QueryStateBoundary`:
   ```tsx
   const { data, isLoading, isError, refetch } = useAgencyHealth();
   return (
     <QueryStateBoundary isLoading={isLoading} isError={isError} hasData={!!data} onRetry={refetch}>
       {data && <HealthContent data={data} />}
     </QueryStateBoundary>
   );
   ```
2. **SSE stuck-stream timeout.** `sendChatQuerySSE` awaits `reader.read()` with no idle deadline. Add a per-read watchdog that aborts the controller and emits `onError` after N ms of silence:
   ```tsx
   const idle = setTimeout(() => controller.abort(new DOMException('idle', 'TimeoutError')), STREAM_IDLE_TIMEOUT_MS);
   const { done, value } = await reader.read();
   clearTimeout(idle);
   ```
   `useChat` already surfaces a connection-lost bubble on non-`done` end, so a timed-out stream reuses that path.
3. **Dashboard error visibility.** 6 polled queries with no `isError`; failed charts render `undefined` into recharts. Add a top-of-page error banner when any critical query `isError`, keep stale data visible.
4. **Wizard / edit validation.** Replace imperative `.trim()` checks with a shared zod `agencySchema`: validate `endpointUrl` as URL, reject empty header names, coerce numeric fields. Gate "next"/save on `safeParse`. Reuse the same schema in detail edit tabs (`ConnectionTab`, `RoutingTab`).

### right — structure & dedup

5. **God-component splits** (characterization tests first): `ApiKeysPage` (370) → list + 4 dialog components; `HistoryPage` (297) → filter bar + list + dialogs; extract `FieldInput` from `SettingsPage`; extract dup `ChartTooltip`.
6. **Split `useChat`** into `useChatStream` (SSE wiring, `streamingState`, abort/timeout) and `useChat` (messages, input, ratings). Same public return shape.
7. **`usePaginatedFilter` hook** to replace the near-identical `useState(page)+useMemo(filter)+useMemo(slice)+totalPages` blocks in `HistoryPage`, `ConnectionLogsPage`, `AuditLogPage`.
8. **Centralise constants.** `shared/constants/query.ts` (`REFETCH.fast/normal/slow`, `STALE_TIME.*`, `PAGE_SIZE.*`) and `shared/constants/status.ts` (single source for status label/colour/variant; have `api-keys`/`health`/`status` import it). Delete dead `allAgencies` in `HistoryPage`.

### fast — wasted work

9. **Route code-splitting.** `App.tsx` statically imports ~25 page modules. Convert each route element to `React.lazy` and wrap `<Routes>` in `<Suspense fallback={<RouteFallback/>}>`. Shrinks initial bundle; routes load on demand.
10. **Server-side filter/paginate.** `HistoryPage` paginates the entire conversation list client-side and date-filters in `useMemo`; once the backend exposes `date_from`/`date_to`/`page`/`page_size` (see Backend dependencies), pass them as query params and drop the client-side `slice`/`filter`. Same for connection-logs status/type filters where the backend gains params.
11. **Memoize hot components.** Wrap pure presentational rows/cards rendered in lists/charts (`MessageBubble`, `AgencyCard`, `DashboardStatsRow`, `LiveActivityChart` children) in `React.memo`; `useCallback` the handlers passed into them. No `React.memo` exists today.
12. **Polling sanity.** Route every `refetchInterval`/`staleTime` through `REFETCH`/`STALE_TIME` tiers; the 5s realtime poll and 15s health poll keep their values but become named.

## Behavior Changes

- **Health / Heatmap:** failed fetch now shows an error card with a retry button instead of an indefinite skeleton.
- **Dashboard:** failed queries now show an error banner; charts no longer receive `undefined`.
- **Feedback:** fetch failure now shows an error+retry, distinct from the genuine empty state.
- **Connection logs:** failed fetch shows an error row instead of the same "ไม่พบข้อมูล" used for genuine empties.
- **Chat SSE:** a stream idle for `STREAM_IDLE_TIMEOUT_MS` is aborted and surfaces a connection-lost bubble instead of a spinner that never resolves.
- **Agency wizard / edit:** invalid endpoint URLs and empty header names are now rejected at the step/save boundary (previously accepted, filtered silently at save).
- **History pagination:** when wired to server-side params, paging fetches a page at a time; the visible page contents are unchanged for existing data sizes.

## Backend dependencies (cross-ref: `2026-06-23-backend-refactor`)

The FAST tier's server-side filtering relies on backend params owned by that spec; FE consumes, does not define them:
- `GET /api/v1/conversations` — add `date_from`, `date_to`, `page`, `page_size`, `total` in response (replaces client-side `slice`/date `useMemo` in `HistoryPage`).
- `GET /api/v1/connection-logs` — add server-side `status`, `connection_type`, `agency_id` filters (page already paginates).
- If these are not yet available, the FE keeps the current client-side path behind `usePaginatedFilter` and switches the data source with no UI change.

## Testing strategy (characterization-first + CI)

- **CI foundation (do first):** add `- run: pnpm test` (i.e. `vitest run`) to the `frontend` job in `.github/workflows/test.yml`, after `tsc --noEmit`. Wire MSW globally in `src/test/setup.ts` (`beforeAll(server.listen)`, `afterEach(server.resetHandlers)`, `afterAll(server.close)`) so suites don't each start it. Confirm `pnpm test` is green locally before/after every refactor task.
- **Characterization-first for risky splits:** before splitting `ApiKeysPage`, `HistoryPage`, or `useChat`, add behaviour/snapshot tests (MSW-backed render, exercise dialogs/filter/paginate, assert visible rows + interactions) so the split is provably behaviour-preserving. Pages already have `*.test.tsx` (e.g. `DashboardPage.test.tsx`, `ApiKeysPage.test.tsx`) — extend rather than replace.
- **TDD for new behaviour:** write failing tests first for each error-state addition (assert error card + retry), the SSE idle timeout (fake timers + a hung MSW stream), and zod validation (reject bad URL / empty header name).
- Run `pnpm test` and `pnpm exec tsc --noEmit` after every task; keep tasks independently shippable so a green suite gates each PR into `dev`.
