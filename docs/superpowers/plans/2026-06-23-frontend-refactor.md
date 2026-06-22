# Frontend Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `frontend/src` correct (real error states + SSE timeout + stronger validation), well-structured (god-component/hook splits, shared hooks/constants), and fast (route code-splitting, memoization, server-side filtering) — gated by the frontend Vitest suite, which is wired into CI as the first step.

**Architecture:** Feature folders under `src/features/*` stay; add a thin `src/shared/{constants,hooks,components}` layer. No global store, no new fetch abstraction. Sequence: branch → CI wires test run + global MSW → WORK (error/loading, SSE timeout, validation) → RIGHT (component/hook decomposition, shared hooks/constants) → FAST (code splitting, memo, server-side filtering). Characterization tests precede each god-component split.

**Tech Stack:** React 18, TypeScript, Vite, React Router v6, TanStack Query v5, Tailwind, shadcn/ui, Vitest + Testing Library + MSW. Package manager: **pnpm 11.5.0** (CI uses `pnpm`, Node 22; `frontend/pnpm-lock.yaml` is the committed lockfile). Run commands from `frontend/`.

---

## File Map

**Created:**
- `frontend/src/shared/constants/query.ts` — `REFETCH`, `STALE_TIME`, `PAGE_SIZE`
- `frontend/src/shared/constants/status.ts` — canonical status label/colour/variant maps
- `frontend/src/shared/components/QueryStateBoundary.tsx`
- `frontend/src/shared/components/QueryStateBoundary.test.tsx`
- `frontend/src/shared/hooks/usePaginatedFilter.ts`
- `frontend/src/shared/hooks/usePaginatedFilter.test.ts`
- `frontend/src/shared/components/FieldInput.tsx`
- `frontend/src/shared/components/ChartTooltip.tsx`
- `frontend/src/features/chat/useChatStream.ts`
- `frontend/src/features/agencies/agencySchema.ts`
- `frontend/src/features/agencies/agencySchema.test.ts`
- `frontend/src/features/api-keys/{ApiKeyList,CreateApiKeyDialog,EditApiKeyDialog,RevealKeyDialog,DeleteApiKeyDialog}.tsx`

**Modified:**
- `.github/workflows/test.yml` (add `pnpm test` to `frontend` job)
- `frontend/src/test/setup.ts` (global MSW lifecycle)
- `frontend/src/features/chat/chatApi.ts` (SSE idle timeout)
- `frontend/src/features/chat/useChat.ts` (consume `useChatStream`)
- `frontend/src/features/{health,heatmap,dashboard,feedback}/*Page.tsx` (`QueryStateBoundary`)
- `frontend/src/features/connection-logs/ConnectionLogsTable.tsx` (error row)
- `frontend/src/features/{health,heatmap,dashboard,connection-logs,executive}/use*.ts` (`REFETCH`/`STALE_TIME`)
- `frontend/src/features/agencies/wizard/AgencyWizardPage.tsx` + `agencyForm.ts` (zod gating)
- `frontend/src/features/agencies/detail/{ConnectionTab,RoutingTab}.tsx` (zod gating)
- `frontend/src/features/api-keys/ApiKeysPage.tsx` (compose split components)
- `frontend/src/features/history/HistoryPage.tsx`, `features/audit/AuditLogPage.tsx`, `features/connection-logs/ConnectionLogsPage.tsx` (`usePaginatedFilter`, `PAGE_SIZE`)
- `frontend/src/features/settings/SettingsPage.tsx` (use shared `FieldInput`)
- `frontend/src/App.tsx` (`React.lazy` + `Suspense`)
- `frontend/src/features/{chat/MessageBubble,agencies/AgencyCard,dashboard/DashboardStatsRow}.tsx` (`React.memo`)

**Deleted:**
- dead `allAgencies` array in `HistoryPage.tsx` (lines ~68, commented usage ~114-121)

---

## Task 1: Branch + wire frontend tests into CI + global MSW

**Files:** `.github/workflows/test.yml`, `frontend/src/test/setup.ts`, `frontend/src/mocks/server.ts`

- [ ] **Step 1: Create branch**
```bash
rtk git checkout -b refactor/frontend-work-right-fast
```

- [ ] **Step 2: Confirm baseline is green locally**
```bash
cd frontend && pnpm install --frozen-lockfile && pnpm test
```
Expected: all suites pass (30 test files). If MSW-backed suites already call `server.listen` per file, they pass today.

- [ ] **Step 3: Wire MSW globally in `src/test/setup.ts`** (append after existing jsdom shims)
```ts
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "@/mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```
Then remove per-file `server.listen/resetHandlers/close` from individual suites only if duplicated; `server.use(...)` overrides stay.

- [ ] **Step 4: Add `pnpm test` to the CI `frontend` job** in `.github/workflows/test.yml` (after the `tsc --noEmit` line)
```yaml
      - run: pnpm exec tsc --noEmit
      - run: pnpm test
```

- [ ] **Step 5: Verify**
```bash
cd frontend && pnpm exec tsc --noEmit && pnpm test
```
Expected: tsc clean, vitest green with global MSW.

- [ ] **Step 6: Commit**
```bash
rtk git add -A && rtk git commit -m "ci(frontend): run vitest in CI; wire MSW globally in test setup"
```

---

## Task 2: Shared QueryStateBoundary (TDD) + fix Health/Heatmap silent failure

**Files:** `shared/components/QueryStateBoundary.tsx` (+ test), `features/health/HealthPage.tsx`, `features/heatmap/HeatmapPage.tsx`

- [ ] **Step 1: Failing test** `shared/components/QueryStateBoundary.test.tsx`
```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryStateBoundary } from "./QueryStateBoundary";

it("shows retry on error and calls onRetry", () => {
  const onRetry = vi.fn();
  render(<QueryStateBoundary isLoading={false} isError hasData={false} onRetry={onRetry}>x</QueryStateBoundary>);
  fireEvent.click(screen.getByRole("button", { name: /ลองอีกครั้ง/ }));
  expect(onRetry).toHaveBeenCalled();
});
```
```bash
cd frontend && rtk vitest run src/shared/components/QueryStateBoundary.test.tsx
```
Expected: fails (module not found).

- [ ] **Step 2: Implement `QueryStateBoundary.tsx`** — props `{isLoading; isError; hasData; onRetry?; loading?; children}`; render skeleton/spinner when loading, an error card with `AlertCircle` + "ลองอีกครั้ง" button when `isError`, else `children`. Mirror the existing `ExecutivePage` error card markup.

- [ ] **Step 3: Confirm pass**
```bash
cd frontend && rtk vitest run src/shared/components/QueryStateBoundary.test.tsx
```

- [ ] **Step 4: Use it in Health/Heatmap.** Replace `if (isLoading || !data) return <Skeleton/>` with destructuring `isError`/`refetch` and wrapping content in `QueryStateBoundary`. Move existing JSX into a `*Content({ data })` block.

- [ ] **Step 5: Verify**
```bash
cd frontend && rtk vitest run && rtk vitest run -- src/features/health src/features/heatmap
```

- [ ] **Step 6: Commit**
```bash
rtk git add -A && rtk git commit -m "feat(frontend): QueryStateBoundary; fix Health/Heatmap infinite skeleton on fetch error"
```

---

## Task 3: Dashboard, Feedback, Connection-logs error states (TDD)

**Files:** `features/dashboard/DashboardPage.tsx` (+ existing `DashboardPage.test.tsx`), `features/feedback/FeedbackPage.tsx` (+ `FeedbackPage.test.tsx`), `features/connection-logs/ConnectionLogsTable.tsx`

- [ ] **Step 1: Failing tests** — override MSW to 500 and assert an error banner/row appears, e.g.
```tsx
server.use(http.get("*/api/v1/dashboard/stats", () => HttpResponse.json({}, { status: 500 })));
// expect screen.findByText(/เกิดข้อผิดพลาด|ลองอีกครั้ง/) on Dashboard render
```
```bash
cd frontend && rtk vitest run src/features/dashboard src/features/feedback
```
Expected: fail.

- [ ] **Step 2: Implement** — Dashboard: derive `const anyError = [statsQ, trendQ, ...].some(q => q.isError)`, render an error banner above charts while keeping last-good data. Feedback: branch `isError` to error+retry, distinct from `!stats` empty state. ConnectionLogsTable: add an `isError` row separate from the empty "ไม่พบข้อมูล".

- [ ] **Step 3: Verify**
```bash
cd frontend && rtk vitest run
```

- [ ] **Step 4: Commit**
```bash
rtk git add -A && rtk git commit -m "feat(frontend): error+retry UI on Dashboard, Feedback, Connection logs"
```

---

## Task 4: SSE idle timeout (TDD)

**Files:** `features/chat/chatApi.ts`, `features/chat/useChat.test.tsx`

- [ ] **Step 1: Add constant** `STREAM_IDLE_TIMEOUT_MS` to `shared/constants/query.ts` (e.g. `30_000`).

- [ ] **Step 2: Failing test** — with `vi.useFakeTimers()`, MSW returns a stream that emits one `step` then hangs; assert `onError`/connection-lost path fires after advancing past the timeout.
```bash
cd frontend && rtk vitest run src/features/chat/useChat.test.tsx
```
Expected: fail (hangs / never errors).

- [ ] **Step 3: Implement** in the `sendChatQuerySSE` read loop — arm a `setTimeout` before each `reader.read()` that calls `controller.abort(new DOMException('idle','TimeoutError'))`, clear it after each successful read, treat the abort as stream-end so `useChat` shows the existing connection-lost bubble.

- [ ] **Step 4: Verify**
```bash
cd frontend && rtk vitest run src/features/chat
```

- [ ] **Step 5: Commit**
```bash
rtk git add -A && rtk git commit -m "fix(chat): abort SSE stream after idle timeout instead of hanging"
```

---

## Task 5: Agency zod schema + wizard/edit validation (TDD)

**Files:** `features/agencies/agencySchema.ts` (+ test), `features/agencies/agencyForm.ts`, `wizard/AgencyWizardPage.tsx`, `detail/ConnectionTab.tsx`, `detail/RoutingTab.tsx`

- [ ] **Step 1: Failing test** `agencySchema.test.ts` — reject empty name, malformed `endpointUrl`, header with empty `name`; accept a valid payload.
```bash
cd frontend && rtk vitest run src/features/agencies/agencySchema.test.ts
```
Expected: fail.

- [ ] **Step 2: Implement `agencySchema.ts`** with zod: `name` non-empty, `endpointUrl` `z.string().url()`, `apiHeaders` each `{ name: z.string().min(1), value: z.string().min(1) }`, numeric fields `z.coerce.number().int().positive().optional()`.

- [ ] **Step 3: Gate UI** — replace imperative `isStepConnectionValid` etc. in `agencyForm.ts` / `AgencyWizardPage.tsx` with `agencySchema.safeParse`; gate "ถัดไป"/save on success. Reuse in `ConnectionTab`/`RoutingTab` save handlers. Extend `wizardFlow.test.tsx` to assert the next button stays disabled for a bad URL.

- [ ] **Step 4: Verify**
```bash
cd frontend && rtk vitest run src/features/agencies && rtk vitest run
```

- [ ] **Step 5: Commit**
```bash
rtk git add -A && rtk git commit -m "feat(agencies): zod validation for wizard + edit (URL, headers, numerics)"
```

---

## Task 6: Centralise constants + dedup status labels

**Files:** `shared/constants/query.ts`, `shared/constants/status.ts`, all `use*.ts` with `refetchInterval`/`staleTime`, `api-keys/ApiKeysPage.tsx`, `health/HealthPage.tsx`, `status/StatusPage.tsx`, `history/HistoryPage.tsx`

- [ ] **Step 1: Create `query.ts`** — `REFETCH = { fast: 15_000, normal: 30_000, slow: 60_000 }`, `STALE_TIME = { ... }`, `PAGE_SIZE = { history: 10, connectionLogs: 20, audit: 50 }`, `STREAM_IDLE_TIMEOUT_MS`.

- [ ] **Step 2: Create `status.ts`** — re-export the canonical maps from `agencies/lifecycle.ts` and add API-key status labels; replace inline maps in `ApiKeysPage`, `HealthPage`, `StatusPage`.

- [ ] **Step 3: Replace literals** — point every `refetchInterval`/`staleTime` and the 3 `PAGE_SIZE` constants at the shared values. Delete the dead `allAgencies` array + its commented block in `HistoryPage`.

- [ ] **Step 4: Verify**
```bash
cd frontend && rtk vitest run && pnpm exec tsc --noEmit
```

- [ ] **Step 5: Commit**
```bash
rtk git add -A && rtk git commit -m "refactor(frontend): centralise query config + status labels; drop dead history agency list"
```

---

## Task 7: usePaginatedFilter hook (TDD) + adopt in 3 pages

**Files:** `shared/hooks/usePaginatedFilter.ts` (+ test), `history/HistoryPage.tsx`, `audit/AuditLogPage.tsx`, `connection-logs/ConnectionLogsPage.tsx`

- [ ] **Step 1: Failing test** — `usePaginatedFilter(items, { pageSize, filter })` returns `{ page, setPage, totalPages, pageItems, total }`; assert slicing, page clamping, and filter application.
```bash
cd frontend && rtk vitest run src/shared/hooks/usePaginatedFilter.test.ts
```

- [ ] **Step 2: Implement** the generic hook (mirror the existing `useMemo` filter + `slice` + `totalPages` math from `HistoryPage`).

- [ ] **Step 3: Adopt** in HistoryPage, ConnectionLogsPage, AuditLogPage (Audit uses offset → adapt). Keep their `*.test.tsx` green (these are the characterization tests for this refactor).

- [ ] **Step 4: Verify**
```bash
cd frontend && rtk vitest run
```

- [ ] **Step 5: Commit**
```bash
rtk git add -A && rtk git commit -m "refactor(frontend): extract usePaginatedFilter; dedup list filter/paginate"
```

---

## Task 8: Characterization tests + split ApiKeysPage

**Files:** `api-keys/ApiKeysPage.test.tsx`, new `api-keys/{ApiKeyList,CreateApiKeyDialog,EditApiKeyDialog,RevealKeyDialog,DeleteApiKeyDialog}.tsx`, `ApiKeysPage.tsx`

- [ ] **Step 1: Strengthen characterization test first** — render `ApiKeysPage` with MSW, assert: list rows render, create dialog submits, edit renames, revoke confirms, delete confirms, reveal dialog shows once. Run and confirm green against current code.
```bash
cd frontend && rtk vitest run src/features/api-keys/ApiKeysPage.test.tsx
```

- [ ] **Step 2: Extract** the four dialogs + list into components; `ApiKeysPage` keeps queries/mutations and composes them. Behaviour unchanged.

- [ ] **Step 3: Verify same test still green (no edits to assertions)**
```bash
cd frontend && rtk vitest run src/features/api-keys
```

- [ ] **Step 4: Commit**
```bash
rtk git add -A && rtk git commit -m "refactor(api-keys): split ApiKeysPage into list + dialog components (char tests first)"
```

---

## Task 9: Split useChat into useChatStream + useChat

**Files:** `features/chat/useChatStream.ts`, `features/chat/useChat.ts`, `features/chat/useChat.test.tsx`

- [ ] **Step 1: Confirm `useChat.test.tsx` covers** send/stream/finalize/cancel/rate; extend if a path is uncovered. Run green first.
```bash
cd frontend && rtk vitest run src/features/chat/useChat.test.tsx
```

- [ ] **Step 2: Extract `useChatStream`** — owns `streamingState`, `streamingRef`, abort/timeout, the `applyAndSet` callbacks and `finalizeStreaming`. `useChat` keeps `messages`, `input`, `handleRate`, `reset`, and calls `useChatStream`. Public return shape of `useChat` unchanged.

- [ ] **Step 3: Verify (same assertions)**
```bash
cd frontend && rtk vitest run src/features/chat
```

- [ ] **Step 4: Commit**
```bash
rtk git add -A && rtk git commit -m "refactor(chat): split streaming lifecycle into useChatStream"
```

---

## Task 10: Extract FieldInput + ChartTooltip

**Files:** `shared/components/FieldInput.tsx`, `shared/components/ChartTooltip.tsx`, `settings/SettingsPage.tsx`, `dashboard/DashboardPage.tsx`, `dashboard/LiveActivityChart.tsx`

- [ ] **Step 1:** Move inline `FieldInput` out of `SettingsPage` (lines ~22-90) into `shared/components/FieldInput.tsx`; import it back.
- [ ] **Step 2:** Move the duplicated chart tooltip (DashboardPage + LiveActivityChart) into `shared/components/ChartTooltip.tsx`; import in both.
- [ ] **Step 3: Verify**
```bash
cd frontend && rtk vitest run && pnpm exec tsc --noEmit
```
- [ ] **Step 4: Commit**
```bash
rtk git add -A && rtk git commit -m "refactor(frontend): extract shared FieldInput and ChartTooltip"
```

---

## Task 11: Route code-splitting

**Files:** `frontend/src/App.tsx`

- [ ] **Step 1:** Convert each page import to `const X = lazy(() => import("@/features/.../XPage"))` (default exports already exist). Wrap `<Routes>` in `<Suspense fallback={<RouteFallback/>}>`. Keep `ProtectedRoute`/`AppLayout` eager.
- [ ] **Step 2: Verify build + tests**
```bash
cd frontend && rtk vitest run && rtk next build 2>/dev/null || pnpm build
```
Expected: build emits multiple route chunks; tests green.
- [ ] **Step 3: Commit**
```bash
rtk git add -A && rtk git commit -m "perf(frontend): lazy-load routes with Suspense"
```

---

## Task 12: Memoize hot components

**Files:** `chat/MessageBubble.tsx`, `agencies/AgencyCard.tsx`, `dashboard/DashboardStatsRow.tsx` (and list children)

- [ ] **Step 1:** Wrap these pure presentational components in `React.memo`; `useCallback` the handlers passed from their parents (e.g. `onRate` in chat, `onSelect` in lists). Verify no prop identity churn defeats memo.
- [ ] **Step 2: Verify**
```bash
cd frontend && rtk vitest run && pnpm exec tsc --noEmit
```
- [ ] **Step 3: Commit**
```bash
rtk git add -A && rtk git commit -m "perf(frontend): memoize hot list/chat components"
```

---

## Task 13: Server-side filter/paginate for History (+ Connection logs) — depends on backend

**Files:** `features/history/useChatHistory.ts`, `historyApi.ts`, `HistoryPage.tsx`; `features/connection-logs/useConnectionLogs.ts`

> Depends on `2026-06-23-backend-refactor` exposing `date_from/date_to/page/page_size/total` on `/api/v1/conversations` and filters on `/api/v1/connection-logs`. If unavailable, skip and leave `usePaginatedFilter` in place.

- [ ] **Step 1: Failing test** — assert the history query sends `date_from`/`date_to`/`page` params (MSW captures request URL) and renders the server `total`.
- [ ] **Step 2: Implement** — pass filter/date/page into the query key + request params; drop the client-side date `useMemo` and `slice` from `HistoryPage`; keep `usePaginatedFilter` only for purely-client lists.
- [ ] **Step 3: Verify**
```bash
cd frontend && rtk vitest run
```
- [ ] **Step 4: Commit + open PR into dev**
```bash
rtk git add -A && rtk git commit -m "perf(history): move date filter + pagination server-side"
rtk git push -u origin refactor/frontend-work-right-fast
rtk gh pr create --base dev --title "refactor(frontend): work/right/fast pass" --body "Error states, SSE timeout, zod validation, shared hooks/constants, code splitting, server-side history filtering. CI now runs vitest."
```

---

## Final verification

- [ ] `cd frontend && pnpm exec tsc --noEmit && pnpm test` all green
- [ ] CI `frontend` job runs `pnpm test` (Task 1)
- [ ] No new `if (isLoading || !data)` infinite-skeleton patterns remain on data pages
- [ ] `rg "React.lazy|lazy\(" src/App.tsx` shows lazy routes; `rg "refetchInterval|PAGE_SIZE" src/features` shows imports from `shared/constants` only
