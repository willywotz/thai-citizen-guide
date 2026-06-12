# Feedback Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the full feedback analytics off the dashboard into a dedicated, admin-only `/feedback` page, leaving only the four summary cards (plus a link) on the dashboard.

**Architecture:** New `frontend/src/features/feedback/` folder holds the moved `useFeedbackStats` hook, an extracted `CustomTooltip`, a reusable `FeedbackSummaryCards` component (used by both the dashboard and the page), and the page itself. The old `dashboard/FeedbackAnalytics.tsx` is deleted; its charts/low-rated list move into `FeedbackPage`. Wiring touches `App.tsx` (admin-gated route) and `AppSidebar.tsx` (admin nav item). No backend changes.

**Tech Stack:** React 18 + TypeScript, React Router v6, TanStack Query, Recharts, Tailwind/shadcn, Vitest + Testing Library + MSW.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `frontend/src/features/feedback/useFeedbackStats.ts` | (moved) React Query hook for `GET /api/v1/feedback/stats`. |
| `frontend/src/features/feedback/chartTooltip.tsx` | (extracted) Shared `CustomTooltip` for the feedback charts. |
| `frontend/src/features/feedback/FeedbackSummaryCards.tsx` | The 4 summary cards; self-contained (own hook call + loading skeleton). Used by dashboard **and** page. |
| `frontend/src/features/feedback/FeedbackPage.tsx` | Default-exported admin page: header → summary cards → 2 charts → low-rated list. |
| `frontend/src/features/dashboard/FeedbackAnalytics.tsx` | **Deleted.** |
| `frontend/src/features/dashboard/useFeedbackStats.ts` | **Deleted** (moved to feedback folder). |
| `frontend/src/features/dashboard/DashboardPage.tsx` | Renders `FeedbackSummaryCards` + link instead of `FeedbackAnalytics`. |
| `frontend/src/App.tsx` | Adds `/feedback` admin route. |
| `frontend/src/shared/components/layout/AppSidebar.tsx` | Adds `ความคิดเห็น` admin nav item. |
| `frontend/src/mocks/fixtures.ts` | Adds `mockFeedbackStats`. |
| `frontend/src/mocks/handlers.ts` | Adds feedback-stats MSW handler. |

All `npm`/`git` commands run from `frontend/` unless noted. Use `rtk` prefixes per project convention.

---

### Task 1: MSW fixture + handler for feedback stats

Test infrastructure so later component tests can mock the stats request. The real `fetchFeedbackStats` maps snake_case → camelCase, so the handler returns **snake_case**.

**Files:**
- Modify: `frontend/src/mocks/fixtures.ts` (append export)
- Modify: `frontend/src/mocks/handlers.ts:6` (import) and the `handlers` array

- [ ] **Step 1: Add the fixture**

Append to `frontend/src/mocks/fixtures.ts`:

```ts
export const mockFeedbackStats = {
  total_ratings: 42,
  up_count: 30,
  down_count: 12,
  satisfaction_rate: 71,
  daily_trend: [
    { date: "01/06", up: 3, down: 1, rate: 75 },
    { date: "02/06", up: 5, down: 2, rate: 71 },
  ],
  low_rated_questions: [
    {
      content: "ทำไมระบบตอบช้า",
      feedback_text: "ไม่ตรงคำถาม",
      agency: "กรมสรรพากร",
      created_at: "2026-06-01T10:00:00Z",
    },
  ],
  agency_breakdown: [
    { agency: "กรมสรรพากร", up: 20, down: 5, rate: 80 },
    { agency: "กรมที่ดิน", up: 10, down: 7, rate: 59 },
  ],
};
```

- [ ] **Step 2: Add the handler**

In `frontend/src/mocks/handlers.ts`, change the fixtures import (line 6) to include `mockFeedbackStats`:

```ts
import { FIXTURE_MCP_TOOLS, makeHistory, mockAgencies, mockFeedbackStats, row } from "./fixtures";
```

Add this handler as the first entry inside the `handlers` array (just after `export const handlers = [`):

```ts
  http.get("*/api/v1/feedback/stats", () => HttpResponse.json(mockFeedbackStats)),
```

- [ ] **Step 3: Verify the suite still passes (no regressions)**

Run: `rtk npm run test`
Expected: PASS (same as before — nothing consumes the new handler yet).

- [ ] **Step 4: Commit**

```bash
rtk git add src/mocks/fixtures.ts src/mocks/handlers.ts
rtk git commit -m "test(feedback): add MSW fixture and handler for feedback stats

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Move hook + extract tooltip into the feedback folder

Mechanical move/extract. The old `dashboard/useFeedbackStats.ts` stays for now (still imported by `FeedbackAnalytics`); it is deleted in Task 6.

**Files:**
- Create: `frontend/src/features/feedback/useFeedbackStats.ts`
- Create: `frontend/src/features/feedback/chartTooltip.tsx`

- [ ] **Step 1: Create the hook**

`frontend/src/features/feedback/useFeedbackStats.ts`:

```ts
import { useQuery } from '@tanstack/react-query';
import { fetchFeedbackStats } from '@/features/chat/feedbackApi';

export function useFeedbackStats() {
  return useQuery({
    queryKey: ['feedbackStats'],
    queryFn: fetchFeedbackStats,
    staleTime: 30 * 1000,
  });
}
```

- [ ] **Step 2: Create the tooltip**

`frontend/src/features/feedback/chartTooltip.tsx`:

```tsx
export const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-card px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} className="text-xs text-muted-foreground">
          {p.name}: <span className="font-semibold text-foreground">{p.value}</span>
        </p>
      ))}
    </div>
  );
};
```

- [ ] **Step 3: Typecheck**

Run: `rtk npx tsc --noEmit`
Expected: PASS (no errors).

- [ ] **Step 4: Commit**

```bash
rtk git add src/features/feedback/useFeedbackStats.ts src/features/feedback/chartTooltip.tsx
rtk git commit -m "refactor(feedback): move useFeedbackStats hook and extract chart tooltip

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: FeedbackSummaryCards (TDD)

The four summary cards, self-contained. Loading → skeleton grid; otherwise render values from stats (zeros are fine when empty).

**Files:**
- Test: `frontend/src/features/feedback/FeedbackSummaryCards.test.tsx`
- Create: `frontend/src/features/feedback/FeedbackSummaryCards.tsx`

- [ ] **Step 1: Write the failing test**

`frontend/src/features/feedback/FeedbackSummaryCards.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { server } from "@/mocks/server";

import { FeedbackSummaryCards } from "./FeedbackSummaryCards";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderCards() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <FeedbackSummaryCards />
    </QueryClientProvider>,
  );
}

describe("FeedbackSummaryCards", () => {
  it("renders the four summary values from stats", async () => {
    renderCards();
    await waitFor(() => expect(screen.getByText("Feedback ทั้งหมด")).toBeInTheDocument());
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("71%")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk npx vitest run src/features/feedback/FeedbackSummaryCards.test.tsx`
Expected: FAIL — cannot resolve `./FeedbackSummaryCards`.

- [ ] **Step 3: Write the component**

`frontend/src/features/feedback/FeedbackSummaryCards.tsx`:

```tsx
import { ThumbsUp, ThumbsDown, TrendingUp } from "lucide-react";

import { Card, CardContent } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { cn } from "@/shared/lib/utils";
import { useFeedbackStats } from "@/features/feedback/useFeedbackStats";

export function FeedbackSummaryCards() {
  const { data: stats, isLoading } = useFeedbackStats();

  if (isLoading || !stats) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }

  const cards = [
    { label: "Feedback ทั้งหมด", value: stats.totalRatings, icon: TrendingUp, color: "text-primary" },
    { label: "👍 พึงพอใจ", value: stats.upCount, icon: ThumbsUp, color: "text-success" },
    { label: "👎 ไม่พึงพอใจ", value: stats.downCount, icon: ThumbsDown, color: "text-destructive" },
    { label: "อัตราความพึงพอใจ", value: `${stats.satisfactionRate}%`, icon: TrendingUp, color: "text-info" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((s, i) => (
        <Card key={i}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">{s.label}</span>
              <s.icon className={cn("h-4 w-4", s.color)} />
            </div>
            <p className="text-2xl font-bold text-foreground">{s.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk npx vitest run src/features/feedback/FeedbackSummaryCards.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/features/feedback/FeedbackSummaryCards.tsx src/features/feedback/FeedbackSummaryCards.test.tsx
rtk git commit -m "feat(feedback): add reusable FeedbackSummaryCards component

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: FeedbackPage (TDD)

The page: header → `FeedbackSummaryCards` → daily-trend line chart + agency-breakdown bar chart → low-rated questions list. Charts/list are moved verbatim from the old `FeedbackAnalytics`. `FeedbackSummaryCards` handles its own loading; the page handles the chart-area loading/empty state.

**Files:**
- Test: `frontend/src/features/feedback/FeedbackPage.test.tsx`
- Create: `frontend/src/features/feedback/FeedbackPage.tsx`

- [ ] **Step 1: Write the failing test**

`frontend/src/features/feedback/FeedbackPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { ThemeProvider } from "next-themes";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { server } from "@/mocks/server";

import FeedbackPage from "./FeedbackPage";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider attribute="class">
        <FeedbackPage />
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

describe("FeedbackPage", () => {
  it("renders summary cards, charts, and low-rated questions from stats", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Feedback ทั้งหมด")).toBeInTheDocument());
    expect(screen.getByText("แนวโน้มความพึงพอใจรายวัน (14 วัน)")).toBeInTheDocument();
    expect(screen.getByText("ความพึงพอใจแยกตามหน่วยงาน")).toBeInTheDocument();
    expect(screen.getByText("คำถามที่ได้คะแนนต่ำ (ล่าสุด)")).toBeInTheDocument();
    expect(screen.getByText("ทำไมระบบตอบช้า")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk npx vitest run src/features/feedback/FeedbackPage.test.tsx`
Expected: FAIL — cannot resolve `./FeedbackPage`.

- [ ] **Step 3: Write the page**

`frontend/src/features/feedback/FeedbackPage.tsx`:

```tsx
import { useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend,
} from "recharts";
import { ThumbsDown, MessageSquareWarning } from "lucide-react";
import { useTheme } from "next-themes";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { useFeedbackStats } from "@/features/feedback/useFeedbackStats";
import { FeedbackSummaryCards } from "@/features/feedback/FeedbackSummaryCards";
import { CustomTooltip } from "@/features/feedback/chartTooltip";

export default function FeedbackPage() {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const { data: stats, isLoading } = useFeedbackStats();

  const colors = useMemo(() => ({
    grid: isDark ? "hsl(220 15% 25%)" : "hsl(214 25% 92%)",
    tick: isDark ? "hsl(215 15% 60%)" : "hsl(215 15% 50%)",
    up: isDark ? "hsl(145 50% 50%)" : "hsl(145 55% 40%)",
    down: isDark ? "hsl(0 60% 55%)" : "hsl(0 65% 50%)",
    rate: isDark ? "hsl(213 65% 60%)" : "hsl(213 70% 45%)",
  }), [isDark]);

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground">ความคิดเห็นและความพึงพอใจ</h2>
        <p className="text-xs text-muted-foreground mt-0.5">วิเคราะห์ Feedback จากผู้ใช้งานระบบ</p>
      </div>

      <FeedbackSummaryCards />

      {isLoading ? (
        <Skeleton className="h-72" />
      ) : !stats || stats.totalRatings === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <MessageSquareWarning className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground">ยังไม่มีข้อมูล Feedback</p>
            <p className="text-xs text-muted-foreground mt-1">ข้อมูลจะแสดงเมื่อผู้ใช้เริ่มให้คะแนนคำตอบ</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">แนวโน้มความพึงพอใจรายวัน (14 วัน)</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={stats.dailyTrend} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: colors.tick }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: colors.tick }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line type="monotone" dataKey="up" name="👍" stroke={colors.up} strokeWidth={2} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="down" name="👎" stroke={colors.down} strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">ความพึงพอใจแยกตามหน่วยงาน</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={stats.agencyBreakdown} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10, fill: colors.tick }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="agency" width={100} tick={{ fontSize: 10, fill: colors.tick }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="up" name="👍" stackId="a" fill={colors.up} radius={[0, 0, 0, 0]} />
                    <Bar dataKey="down" name="👎" stackId="a" fill={colors.down} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          {stats.lowRatedQuestions.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">คำถามที่ได้คะแนนต่ำ (ล่าสุด)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {stats.lowRatedQuestions.map((q, i) => (
                    <div key={i} className="flex items-start gap-3 p-3 bg-destructive/5 border border-destructive/10 rounded-lg">
                      <ThumbsDown className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-foreground line-clamp-2">{q.content}</p>
                        {q.feedback_text && (
                          <p className="text-xs text-muted-foreground mt-1 italic">"{q.feedback_text}"</p>
                        )}
                        <div className="flex items-center gap-2 mt-1.5">
                          <span className="text-[10px] bg-muted px-2 py-0.5 rounded-full">{q.agency}</span>
                          <span className="text-[10px] text-muted-foreground">
                            {new Date(q.created_at).toLocaleDateString('th-TH')}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk npx vitest run src/features/feedback/FeedbackPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add src/features/feedback/FeedbackPage.tsx src/features/feedback/FeedbackPage.test.tsx
rtk git commit -m "feat(feedback): add dedicated FeedbackPage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Wire the route and sidebar nav item

Register `/feedback` as an admin-only route and add the admin sidebar item.

**Files:**
- Modify: `frontend/src/App.tsx` (import + route)
- Modify: `frontend/src/shared/components/layout/AppSidebar.tsx` (icon import + `adminItems`)

- [ ] **Step 1: Add the route to `App.tsx`**

Add the import alongside the other feature-page imports (near line 27):

```tsx
import FeedbackPage from "@/features/feedback/FeedbackPage";
```

Add this route inside the `<AppLayout />` block, immediately after the `/users` route (around line 63):

```tsx
<Route path="/feedback" element={<ProtectedRoute requireAdmin><FeedbackPage /></ProtectedRoute>} />
```

- [ ] **Step 2: Add the sidebar item to `AppSidebar.tsx`**

Add `MessageSquareWarning` to the existing `lucide-react` import (line 1):

```tsx
import { MessageSquare, LayoutDashboard, Building2, History, Network, LogOut, Activity, KeyRound, Briefcase, Flame, Settings, Users, MessageSquareWarning } from "lucide-react";
```

Add an entry to the `adminItems` array (lines 33-36) so it reads:

```ts
const adminItems = [
  { title: "ความคิดเห็น", url: "/feedback", icon: MessageSquareWarning },
  { title: "จัดการผู้ใช้", url: "/users", icon: Users },
  { title: "ตั้งค่าระบบ", url: "/settings", icon: Settings },
];
```

- [ ] **Step 3: Typecheck**

Run: `rtk npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
rtk git add src/App.tsx src/shared/components/layout/AppSidebar.tsx
rtk git commit -m "feat(feedback): add admin-only /feedback route and sidebar item

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Switch dashboard to summary cards + delete old files (TDD)

Replace `FeedbackAnalytics` on the dashboard with `FeedbackSummaryCards` + a "ดูทั้งหมด →" link, then delete the now-dead `FeedbackAnalytics.tsx` and `dashboard/useFeedbackStats.ts`.

**Files:**
- Test: `frontend/src/features/dashboard/DashboardPage.test.tsx`
- Modify: `frontend/src/features/dashboard/DashboardPage.tsx`
- Delete: `frontend/src/features/dashboard/FeedbackAnalytics.tsx`
- Delete: `frontend/src/features/dashboard/useFeedbackStats.ts`

- [ ] **Step 1: Write the failing test**

`frontend/src/features/dashboard/DashboardPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { ThemeProvider } from "next-themes";
import { MemoryRouter } from "react-router-dom";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { server } from "@/mocks/server";

import DashboardPage from "./DashboardPage";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider attribute="class">
        <MemoryRouter initialEntries={["/dashboard"]}>
          <DashboardPage />
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

describe("DashboardPage feedback section", () => {
  it("shows the summary cards and a link to the feedback page", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Feedback ทั้งหมด")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /ดูทั้งหมด/ })).toHaveAttribute("href", "/feedback");
  });

  it("no longer renders the full feedback charts or low-rated list", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Feedback ทั้งหมด")).toBeInTheDocument());
    expect(screen.queryByText("แนวโน้มความพึงพอใจรายวัน (14 วัน)")).not.toBeInTheDocument();
    expect(screen.queryByText("คำถามที่ได้คะแนนต่ำ (ล่าสุด)")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk npx vitest run src/features/dashboard/DashboardPage.test.tsx`
Expected: FAIL — the dashboard still renders `<FeedbackAnalytics />`, so the low-rated/charts headings are present and the link is missing.

- [ ] **Step 3: Update `DashboardPage.tsx`**

Replace the import line (line 12):

```tsx
import { FeedbackAnalytics } from "./FeedbackAnalytics";
```

with:

```tsx
import { Link } from "react-router-dom";
import { FeedbackSummaryCards } from "@/features/feedback/FeedbackSummaryCards";
```

Replace `<FeedbackAnalytics />` (line 192) with:

```tsx
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-foreground">📊 Feedback</h3>
          <Link to="/feedback" className="text-xs text-primary hover:underline">ดูทั้งหมด →</Link>
        </div>
        <FeedbackSummaryCards />
      </div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk npx vitest run src/features/dashboard/DashboardPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Delete the dead files**

```bash
rtk git rm src/features/dashboard/FeedbackAnalytics.tsx src/features/dashboard/useFeedbackStats.ts
```

- [ ] **Step 6: Confirm nothing else imports the deleted modules**

Run: `rtk grep "dashboard/useFeedbackStats\|dashboard/FeedbackAnalytics\|FeedbackAnalytics" src`
Expected: no matches (other than any in this plan/docs). If a match appears, update that import to `@/features/feedback/...` before continuing.

- [ ] **Step 7: Typecheck + full test suite**

Run: `rtk npx tsc --noEmit && rtk npm run test`
Expected: PASS — no dangling imports, all tests green.

- [ ] **Step 8: Commit**

```bash
rtk git add src/features/dashboard/DashboardPage.tsx src/features/dashboard/DashboardPage.test.tsx
rtk git commit -m "refactor(dashboard): show feedback summary cards + link, remove embedded analytics

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Final verification

- [ ] **Step 1: Lint**

Run: `rtk lint` (or `rtk npm run lint`)
Expected: no new violations in the touched files.

- [ ] **Step 2: Full test suite**

Run: `rtk npm run test`
Expected: PASS.

- [ ] **Step 3: Production build sanity check**

Run: `rtk next build` is N/A (Vite). Run: `rtk npm run build`
Expected: build succeeds.

- [ ] **Step 4: Manual smoke (optional, via `/run` or dev server)**

As an admin user: `/feedback` shows the page with charts; the sidebar shows `ความคิดเห็น`; the dashboard shows the 4 summary cards with a working "ดูทั้งหมด →" link; non-admins do not see the nav item and are blocked from the route.

---

## Self-Review Notes

- **Spec coverage:** new folder + 4 files (Tasks 2-4), `FeedbackAnalytics` deleted + hook moved (Tasks 2, 6), dashboard summary-only + link (Task 6), admin route (Task 5), admin sidebar item `ความคิดเห็น` (Task 5), no backend changes — all covered.
- **Naming consistency:** `useFeedbackStats`, `FeedbackSummaryCards`, `CustomTooltip`, default-exported `FeedbackPage`, fixture `mockFeedbackStats` are used identically across tasks.
- **Snake_case vs camelCase:** the MSW handler returns snake_case (`total_ratings`, …) because `fetchFeedbackStats` maps to camelCase; component assertions use the mapped values (42 / 30 / 12 / 71%).
- **Intermediate states:** between Tasks 4 and 6 the dashboard still shows the old analytics while the new page exists — harmless; each task's tests pass independently.
