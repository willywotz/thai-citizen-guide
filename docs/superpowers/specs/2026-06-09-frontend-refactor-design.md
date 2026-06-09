# Frontend Refactor Design

**Date:** 2026-06-09
**Scope:** Full frontend restructure — feature-based folders, React Query standardization, page decomposition
**Approach:** Big bang (single PR)

## Goals

1. Migrate from a layer-based structure (`pages/`, `components/`, `hooks/`, `services/`) to a feature-based structure where each feature owns its pages, components, hooks, API functions, and types.
2. Standardize all server-state data fetching on React Query (`useQuery`/`useMutation`).
3. Decompose the four largest page files into focused, single-purpose components.

## Folder Structure

```
src/
  features/
    agencies/         AgenciesPage, AgencyDetailPage + sub-components, useAgencies, agencyApi, types
    api-keys/         ApiKeysPage, apiKeyApi, types
    architecture/     ArchitecturePage (static, no data)
    auth/             LoginPage, SignupPage, ForgotPasswordPage, ResetPasswordPage, ProtectedRoute, useAuth
    chat/             ChatPage + sub-components, useChat, useChatHistory, useConversationMessages, chatApi, feedbackApi, types
    connection-logs/  ConnectionLogsPage + sub-components, useConnectionLogs, types
    dashboard/        DashboardPage + sub-components, useDashboard, useRealtimeActivity, dashboardApi, types
    executive/        ExecutivePage + sub-components, useExecutive, executiveApi, types
    health/           HealthPage, healthApi, types
    heatmap/          HeatmapPage, heatmapApi, types
    history/          HistoryPage + sub-components, historyApi, types
    public/           PublicPortal
    settings/         SettingsPage, settingsApi, types
  shared/
    components/
      layout/         AppLayout, AppSidebar
      ui/             (shadcn components — untouched)
      NavLink.tsx
      ThemeProvider.tsx
      ThemeToggle.tsx
    hooks/
      use-mobile.tsx
      use-toast.ts
      useFeedbackStats.ts
    lib/
      apiClient.ts
      utils.ts
    types/            shared cross-feature types (re-exported from index.ts)
    data/             mockData (dev only)
  App.tsx
  main.tsx
```

## Data Fetching

All server-state hooks use React Query. Service files remain as thin async function layers; hooks wrap them.

**Read pattern:**
```ts
// features/agencies/agencyApi.ts
export const agencyApi = {
  list: () => api.get<Agency[]>('/api/v1/agencies'),
  get: (id: string) => api.get<Agency>(`/api/v1/agencies/${id}`),
};

// features/agencies/useAgencies.ts
export function useAgencies() {
  return useQuery({ queryKey: ['agencies'], queryFn: agencyApi.list });
}
```

**Mutation pattern:**
```ts
export function useUpdateAgency() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: agencyApi.update,
    onSuccess: (_, id) => queryClient.invalidateQueries({ queryKey: ['agencies', id] }),
  });
}
```

**Exception:** `useChat` manages complex SSE streaming state that does not fit `useQuery`. It stays as manual state management, moved into `features/chat/`.

**Hooks to convert to React Query:** `useDashboard`, `useConnectionLogs`, `useAgencies`, `useExecutive`, `useInsights`, `useFeedbackStats`. `useRealtimeActivity` stays manual (real-time subscription).

## Page Decomposition

### AgencyDetailPage (439 lines) → ~5 components
```
features/agencies/
  AgencyDetailPage.tsx        ← routing, data fetching, layout (~60 lines)
  AgencyDetailHeader.tsx      ← name, icon, metadata, status badges
  AgencyDetailStats.tsx       ← stat cards / KPI section
  AgencyConversationList.tsx  ← conversation history table
  AgencyDetailActions.tsx     ← edit/delete/action buttons
```

### ExecutivePage (368 lines) → ~4 components
```
features/executive/
  ExecutivePage.tsx           ← layout, data fetching (~50 lines)
  ExecutiveSummaryCard.tsx    ← summary text/markdown block
  ExecutiveMetricsGrid.tsx    ← KPI grid
  ExecutiveFeedbackTable.tsx  ← feedback breakdown table
```

### DashboardPage (317 lines) → ~4 components
```
features/dashboard/
  DashboardPage.tsx           ← layout, data (~50 lines)
  DashboardStatsRow.tsx       ← top stat cards
  LiveActivityChart.tsx       ← (already exists, moved)
  FeedbackAnalytics.tsx       ← (already exists, moved)
```

### ConnectionLogsPage (348 lines) → ~3 components
```
features/connection-logs/
  ConnectionLogsPage.tsx      ← layout, filters, data (~60 lines)
  ConnectionLogsTable.tsx     ← table + pagination
  ConnectionLogFilters.tsx    ← filter bar
```

Smaller pages (HistoryPage, ApiKeysPage, HeatmapPage, SettingsPage) are reviewed during implementation and extracted only where a clear boundary exists.

## Out of Scope

- Changes to the backend
- Changes to shadcn `ui/` components
- Adding new features or fixing bugs
- Changing routing structure in `App.tsx` (paths stay the same)

## Success Criteria

- All existing routes work identically after the refactor
- No new `any` types introduced
- All hooks that previously used manual fetch state now use `useQuery`/`useMutation` (except `useChat`, `useRealtimeActivity`)
- No file in `features/` exceeds ~200 lines (pages act as thin orchestrators)
- TypeScript compiles without errors
- Existing tests pass
