# Extract Feedback Analytics to Its Own Page

**Date:** 2026-06-12
**Status:** Approved (design)

## Goal

Move the full feedback analytics (daily-trend chart, agency breakdown, low-rated
questions) off the dashboard into a dedicated, admin-only `/feedback` page. The
dashboard retains only the four summary cards plus a link to the new page.

## Motivation

`DashboardPage` currently renders the entire `FeedbackAnalytics` block at the
bottom, mixing high-level usage stats with detailed feedback analytics. Giving
feedback its own page declutters the dashboard and gives the feedback data room
to grow, while keeping an at-a-glance summary on the dashboard.

## Scope

- Frontend only. No backend changes — `GET /api/v1/feedback/stats` is already a
  separate, admin-gated endpoint.

## New Structure — `frontend/src/features/feedback/`

| File | Purpose |
|------|---------|
| `FeedbackSummaryCards.tsx` | The 4 summary cards (Feedback ทั้งหมด / 👍 พึงพอใจ / 👎 ไม่พึงพอใจ / อัตราความพึงพอใจ). Self-contained: calls `useFeedbackStats()`, renders its own loading skeleton and empty state. Consumed by **both** the dashboard and the feedback page. |
| `FeedbackPage.tsx` | Default-exported page. Layout: page header → `<FeedbackSummaryCards />` → daily-satisfaction line chart + agency-breakdown bar chart → low-rated questions list. Owns the loading/empty state for the chart section. |
| `useFeedbackStats.ts` | Moved verbatim from `features/dashboard/useFeedbackStats.ts`. |
| `chartTooltip.tsx` | The `CustomTooltip` helper extracted from `FeedbackAnalytics.tsx` so both the page charts can use it. |

### Removed
- `features/dashboard/FeedbackAnalytics.tsx` — deleted. Its summary block becomes
  `FeedbackSummaryCards`; its charts and low-rated list move into `FeedbackPage`.
- `features/dashboard/useFeedbackStats.ts` — moved (see above).

### Data flow
Both `FeedbackSummaryCards` and `FeedbackPage` call `useFeedbackStats()`. React
Query dedupes by the `['feedbackStats']` query key, so the cards rendered inside
the page reuse the page's single request; on the dashboard the cards issue their
own (shared-cache) request.

## Wiring Changes

### `DashboardPage.tsx`
Replace `<FeedbackAnalytics />` (line 192) with a compact section:

- A heading (e.g. `📊 Feedback`) with a `ดูทั้งหมด →` `Link` to `/feedback`
  on the same row.
- `<FeedbackSummaryCards />` below it.

Remove the now-unused `FeedbackAnalytics` import; add the `FeedbackSummaryCards`
import and `Link` (from `react-router-dom`).

### `App.tsx`
Add an admin-gated route mirroring the existing `/users` route:

```tsx
<Route path="/feedback" element={<ProtectedRoute requireAdmin><FeedbackPage /></ProtectedRoute>} />
```

Add `import FeedbackPage from "@/features/feedback/FeedbackPage";`.

### `AppSidebar.tsx`
Add to the **`adminItems`** array (admin-only rendering already handled by the
`user?.role === "admin"` guard):

```ts
{ title: "ความคิดเห็น", url: "/feedback", icon: MessageSquareWarning }
```

Import `MessageSquareWarning` from `lucide-react`.

## Component Detail

`FeedbackPage` follows the page conventions seen in `DashboardPage`:
wrapper `div` with `p-4 md:p-6 space-y-6`, a header block with a Thai title
(`ความคิดเห็นและความพึงพอใจ`) and subtitle. The charts and low-rated list are
moved unchanged from `FeedbackAnalytics` (same Recharts config, same theme-aware
colors, same `CustomTooltip`).

`FeedbackSummaryCards` keeps the existing card markup and the loading skeleton
for the 4-card grid. Empty state (`stats.totalRatings === 0`): the cards render
zeros; the page's chart section shows the existing "ยังไม่มีข้อมูล Feedback"
empty card.

## Testing (TDD)

The frontend already uses Vitest + `@testing-library/react` + jsdom, with
colocated `*.test.tsx` files (e.g. `AgenciesPage.test.tsx`). Run via
`npm run test` (`vitest run`). New tests follow the same colocated convention
and are written failing-first:

1. `FeedbackPage.test.tsx` — given mocked `useFeedbackStats` data, renders the
   summary cards, both charts, and the low-rated questions list.
2. `DashboardPage.test.tsx` — no longer renders the feedback charts / low-rated
   list; renders the summary cards and a link to `/feedback`.
3. `FeedbackSummaryCards.test.tsx` — renders the four labels and values from
   mocked stats; shows the skeleton while loading.

Existing test patterns (`src/mocks/handlers`, query-client wrappers) will be
reused for mocking the stats request.

## Out of Scope

- Changes to how individual messages are rated (chat `MessageBubble`,
  `FeedbackDialog`, `updateMessageRating`) — untouched.
- Backend endpoints, schemas, and models — untouched.
