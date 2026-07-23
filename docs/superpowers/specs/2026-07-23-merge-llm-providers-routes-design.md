# Design: Merge LLM Providers + Routes into one page

**Date:** 2026-07-23
**Status:** Approved

## Goal

Combine the two separate admin pages — `/llm-providers` and `/llm-routes` — into a
single **"LLM Settings"** page at `/llm-settings`. On the merged page, Routes become
**edit-only**: an admin can no longer create or delete a route, only edit an existing one.
Providers keep full create / edit / delete.

## Layout

- One admin-only page (`requireAdmin`), route path `/llm-settings`.
- Two panels: **Providers (left)** and **Routes (right)**.
  - Mobile: panels stack vertically.
  - Desktop (`md`+): two-column CSS grid, Providers left, Routes right
    (e.g. `grid grid-cols-1 md:grid-cols-2 gap-6`).
- Each panel keeps its own header + list.
  - Providers header keeps the "เพิ่มผู้ให้บริการ" (Add) button.
  - Routes header drops its "เพิ่มเส้นทาง" (Add) button.

## Behavior changes

### Providers — unchanged
Full create / edit / delete. Same list, dialogs, mutations, and toasts.

### Routes — edit-only
- **Remove** the Create button and `CreateLlmRouteDialog` usage.
- **Remove** the per-row Delete button and `DeleteLlmRouteDialog` usage.
- **Remove** the `createMutation` and `deleteMutation`, and the `createOpen` /
  `deleteTarget` state.
- **Keep** the existing Edit flow and `EditLlmRouteDialog` **exactly as-is**
  (provider, model, timeout override, enabled; purpose stays read-only).

## Code structure

Keep the two feature folders; extract the page bodies into reusable panels.

- **New** `frontend/src/features/llm/LlmSettingsPage.tsx`
  - Grid wrapper (`p-4 md:p-6`) rendering `<ProvidersPanel />` and `<RoutesPanel />`.
- **New** `frontend/src/features/llm-providers/ProvidersPanel.tsx`
  - Extracted verbatim from the current `LlmProvidersPage` body (query, mutations,
    dialogs, list). Drop only the outer `p-4 md:p-6` wrapper (the page owns spacing);
    the panel returns its `space-y-4` header + content.
- **New** `frontend/src/features/llm-routes/RoutesPanel.tsx`
  - Extracted from the current `LlmRoutesPage` body, **minus** create + delete
    (state, mutations, buttons, dialogs). Header has no Add button.
- **Edit** `frontend/src/features/llm-routes/LlmRoutesList.tsx`
  - Drop the `onDelete` prop and the Delete `<button>`. Keep the Edit button.
- **Delete** `LlmProvidersPage.tsx`, `LlmRoutesPage.tsx`, and their `.test.tsx`
  (replaced by the panels + a new `LlmSettingsPage.test.tsx`).

`LlmProviderList` is unchanged (Providers keep delete).

## Routing & navigation

- `frontend/src/App.tsx`
  - Replace the `LlmProvidersPage` / `LlmRoutesPage` lazy imports with a single
    `LlmSettingsPage` lazy import.
  - Add one admin route: `/llm-settings` → `<ProtectedRoute requireAdmin><LlmSettingsPage /></ProtectedRoute>`.
  - Redirect old paths so bookmarks don't break: `/llm-providers` and `/llm-routes`
    both `<Navigate to="/llm-settings" replace />` (add `Navigate` to the
    `react-router-dom` import).
- `frontend/src/shared/components/layout/AppSidebar.tsx`
  - Replace the two entries (`LLM Providers`, `LLM Routes`) with a single entry:
    `{ title: "LLM Settings", url: "/llm-settings", icon: Cpu }`.
  - Drop the now-unused `Route` icon import if nothing else uses it.

## Testing (TDD)

- **New** `frontend/src/features/llm/LlmSettingsPage.test.tsx`:
  - Renders both panels (a Providers heading and a Routes heading).
  - Providers panel shows an Add button; Routes panel does **not**.
  - Routes list rows expose an Edit control but **no** Delete control.
- Reuse the existing provider/route test setup (mock API modules) where practical.
- Old page tests are removed with their pages.

## Out of scope

- No backend / API changes. `deleteRoute` / `createRoute` API functions may remain
  in `llmRouteApi.ts` even if unused by the UI (harmless; leave them).
- No changes to provider behavior, the route edit form fields, or purposes handling.
