# Merge admin pages into a tabbed Settings area

**Date:** 2026-07-23
**Status:** Approved (design)

## Problem

Six administrative pages each occupy their own sidebar entry and top-level
route:

| Page | Route | Access |
|------|-------|--------|
| ตั้งค่าระบบ (System Settings) | `/settings` | admin |
| LLM Settings | `/llm-settings` | admin |
| API Keys | `/api-keys` | admin |
| การใช้งาน API Key (Usage) | `/usage` | all roles |
| ประวัติการเชื่อมต่อ (Connection logs) | `/connection-logs` | admin |
| บันทึกการตรวจสอบ (Audit log) | `/audit-log` | admin |

The sidebar is crowded and these related pages are scattered. Goal: present
them as tabs under a single Settings area.

## Non-goals

- No refactor of the six page bodies. This is purely a navigation/composition
  change.
- No backend changes. Access rules already live in `roles.ts` (frontend) and
  the backend allowlist; behaviour is preserved.

## Decisions

- **Routing:** nested routes under a shared layout; each tab is deep-linkable
  and bookmarkable. Old URLs redirect in.
- **Usage access:** all six become tabs, but with a per-tab guard — non-admins
  reaching `/settings` see only the Usage tab; admins see all six.
- **Sidebar:** collapse the six entries into one "ตั้งค่าระบบ" entry.

## Design

### 1. `SettingsLayout` (tab shell)

New `frontend/src/features/settings/SettingsLayout.tsx`:

- Renders a page header + a role-filtered `TabsList` (from
  `@/shared/components/ui/tabs`) and an `<Outlet />` for the active child route.
- Active tab is derived from `location.pathname` — no internal tab state — so
  the tab bar, URL, and browser back button stay in sync.
- Clicking a tab navigates to its child route.

Tab table:

| Tab label | Child path | Component | Access |
|-----------|-----------|-----------|--------|
| ตั้งค่าระบบ | `/settings/system` | `SettingsPage` | admin |
| LLM | `/settings/llm` | `LlmSettingsPage` | admin |
| API Keys | `/settings/api-keys` | `ApiKeysPage` | admin |
| การใช้งาน API Key | `/settings/usage` | `UsageAnalyticsPage` | all |
| ประวัติการเชื่อมต่อ | `/settings/connections` | `ConnectionLogsPage` | admin |
| บันทึกการตรวจสอบ | `/settings/audit` | `AuditLogPage` | admin |

Non-admins see only the Usage tab in the bar. The tab list is filtered with the
same `canAccess(role, path)` helper used by the sidebar, keeping one source of
truth.

Each page component brings its own `p-4 md:p-6` padding and heading, so the
layout only supplies the header + tab bar; panels render the existing
components unchanged.

### 2. Routing (`App.tsx`)

Replace the six top-level routes with one nested tree:

```
/settings                         ProtectedRoute (authenticated) > SettingsLayout
  index                           role redirect: admin -> system, else -> usage
  /settings/system                ProtectedRoute requireAdmin > SettingsPage
  /settings/llm                   ProtectedRoute requireAdmin > LlmSettingsPage
  /settings/api-keys              ProtectedRoute requireAdmin > ApiKeysPage
  /settings/usage                 UsageAnalyticsPage            (all roles)
  /settings/connections           ProtectedRoute requireAdmin > ConnectionLogsPage
  /settings/audit                 ProtectedRoute requireAdmin > AuditLogPage
```

- The parent `/settings` is authenticated-only (no `requireAdmin`) because it
  now contains the all-roles Usage tab.
- Each admin child is individually wrapped in `ProtectedRoute requireAdmin`, so
  a non-admin deep-linking to `/settings/audit` is blocked, not merely hidden
  from the tab bar.
- The `index` route uses a small role-aware redirect component
  (`isAdmin ? /settings/system : /settings/usage`).

Redirects from old routes (each `<Navigate replace>`):

- `/api-keys` -> `/settings/api-keys`
- `/usage` -> `/settings/usage`
- `/connection-logs` -> `/settings/connections`
- `/audit-log` -> `/settings/audit`
- `/llm-settings` -> `/settings/llm`
- `/llm-providers` -> `/settings/llm` (already redirected to `/llm-settings`)
- `/llm-routes` -> `/settings/llm` (already redirected to `/llm-settings`)

### 3. Sidebar + roles

- `AppSidebar.tsx`: remove the six individual `navItems` entries (System
  Settings, LLM Settings, API Keys, Usage, Connection logs, Audit log) and add a
  single `{ title: "ตั้งค่าระบบ", url: "/settings", icon: Settings }`. This
  supersedes the uncommitted reordering currently in the working tree.
- `roles.ts` (`ROUTE_ROLES`): change `/settings` to `ALL` (so non-admins see the
  Settings entry that holds their Usage tab). Add entries for the new child
  paths (`/settings/system`, `/settings/llm`, `/settings/api-keys`,
  `/settings/usage`, `/settings/connections`, `/settings/audit`) with their
  access levels, keeping `ROUTE_ROLES` the single source of truth. Old path
  entries may remain (harmless; routes now redirect).

### 4. Existing page components

Untouched. They remain default exports and keep any self-guards they already
have (e.g. `SettingsPage`'s own `isAdmin` check stays as defense-in-depth).

## Testing (TDD)

New `frontend/src/features/settings/SettingsLayout.test.tsx`:

- Admin sees all six tab triggers.
- Non-admin sees only the Usage tab trigger.
- `/settings` index redirects: admin -> `/settings/system`, non-admin ->
  `/settings/usage`.
- Active tab reflects the current URL (e.g. rendering at `/settings/audit`
  marks the Audit tab active).

Existing per-component tests (`ApiKeysPage.test.tsx`, `AuditLogPage.test.tsx`,
`LlmSettingsPage.test.tsx`, `ConnectionLogsTable.test.tsx`,
`ProvidersPanel.test.tsx`, `RoutesPanel.test.tsx`) are unaffected because the
components are untouched.

## Rollout

Single frontend change set; no data migration. Old bookmarks keep working via
redirects.
