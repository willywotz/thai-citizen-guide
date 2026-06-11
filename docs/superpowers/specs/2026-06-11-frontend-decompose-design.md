# Frontend Decomposition + Tests — Design + Plan

**Date:** 2026-06-11
**Status:** Approved (autonomous run; user chose "decompose aggressively")
**Branch:** `refactor/frontend-decompose`

## Goal

Aggressively decompose the three largest frontend units into focused, independently
understandable pieces, and add vitest coverage for the logic that decomposition exposes —
all behavior-preserving (verified by `tsc --noEmit`, `vitest run`, `eslint`, since no live
runtime is available in this environment).

## Targets & public-API contracts (MUST be preserved exactly)

1. `src/shared/components/ui/sidebar.tsx` (637 lines) — vendored shadcn/ui primitive.
   Public export block (24 symbols) must remain importable from the same path:
   `Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupAction,
   SidebarGroupContent, SidebarGroupLabel, SidebarHeader, SidebarInput, SidebarInset,
   SidebarMenu, SidebarMenuAction, SidebarMenuBadge, SidebarMenuButton, SidebarMenuItem,
   SidebarMenuSkeleton, SidebarMenuSub, SidebarMenuSubButton, SidebarMenuSubItem,
   SidebarProvider, SidebarRail, SidebarSeparator, SidebarTrigger, useSidebar`.
   Importers: `shared/components/layout/AppLayout.tsx`, `AppSidebar.tsx`.

2. `src/features/agencies/AgencyFormDialog.tsx` (452 lines) — app component.
   Public export: `export function AgencyFormDialog(props)`. Importer: `AgenciesPage.tsx`.

3. `src/features/chat/useChat.ts` (372 lines) — app hook.
   Public export: `export function useChat()`. Importers: `ChatPage.tsx`,
   `history/HistoryPage.tsx`, `public/PublicPortal.tsx`.

## Approach (per file)

**sidebar.tsx — measured split (preserve shadcn ergonomics):**
- Extract the context + `SidebarProvider` + `useSidebar` + constants/types into
  `sidebar/context.tsx` (or `use-sidebar.ts`). Group the menu sub-components, group
  sub-components, etc. into logically grouped files under a `sidebar/` directory.
- Convert `sidebar.tsx` into a barrel that re-exports the exact 24-symbol surface, OR move
  to `sidebar/index.tsx` if and only if the import path `@/shared/components/ui/sidebar`
  still resolves (Vite resolves a directory's `index.tsx`). Verify importers still compile.
- Splitting the hook/constants out of the component file resolves the existing
  `react-refresh/only-export-components` warning at sidebar.tsx:636.
- Tests (`sidebar.test.tsx` or `context.test.tsx`): the testable logic is the provider
  state — `useSidebar` throws outside a provider; open/closed toggle; controlled `open`
  prop. Use `@testing-library/react` `renderHook` if available; otherwise test the pure
  state helpers. Do NOT write brittle DOM snapshot tests of every primitive.

**AgencyFormDialog.tsx — decompose freely:**
- Extract logical sections (form sections, the connection-type-specific subforms, the
  spec-parse/test-connection handlers, any pure mappers between form state and the Agency
  payload) into child components and/or a `useAgencyForm` hook + a pure
  `agencyFormMapping.ts` (or similar) helper module.
- Fix the two pre-existing `@typescript-eslint/no-explicit-any` errors (lines 129, 144)
  by giving real types — they are in code being refactored, so fix as a good citizen.
- Tests: cover the extracted PURE logic (form↔payload mapping, validation, default values).
  No live API calls.

**useChat.ts — decompose freely:**
- Split into smaller hooks/helpers by responsibility: e.g. SSE/stream-event parsing,
  message/conversation state updates, request building. Pull pure functions into a testable
  module (e.g. `chatStream.ts` / `chatHelpers.ts`).
- `useChat()` remains the single public hook composing the parts; signature unchanged.
- Tests: cover the extracted pure functions (SSE event parsing, state reducers, payload
  building). Mock fetch/axios where needed; no live backend.

## Verification (run after EACH file; all must stay green)

- `cd frontend && node_modules/.bin/tsc --noEmit` → exit 0 (baseline passes today)
- `cd frontend && node_modules/.bin/vitest run` → all tests pass
- `cd frontend && node_modules/.bin/eslint <changed files>` → no NEW errors; the 2
  pre-existing `any` errors in AgencyFormDialog and the sidebar react-refresh warning
  should be RESOLVED by this work, not increased.

Note: vitest in this WSL environment required installing the linux rollup native binary
(`@rollup/rollup-linux-x64-gnu`) into node_modules — done out-of-band, gitignored, no
tracked-file change.

## Out of Scope

- Visual/behavioral changes (pure structural refactor).
- Backend, analytics, dispatch.
- Restyling, new features, dependency upgrades.
- Re-templating the shadcn sidebar's markup (only relocate, don't redesign).

## Integration

One PR for the whole sub-project (all three files), auto-merged after review + green gates.
