# Agency Management Redesign — Frontend (Sub-project 1) — Design

**Date:** 2026-06-11
**Status:** Approved
**Branch:** `feat/agency-redesign-frontend`

## Goal

Redesign agency management end to end: visual overhaul, new information
architecture, and new functionality (health monitoring, guided setup wizard,
4-state lifecycle, routing controls). Work is split frontend-first:

- **Sub-project 1 (this spec):** full frontend redesign + the agreed API
  contract, running on MSW mock handlers.
- **Sub-project 2 (separate spec):** FastAPI backend implementing the
  contract: lifecycle, health checking for all three connection types with
  history storage, MCP discovery endpoint, routing fields feeding the chat
  router, and the `active/inactive → active/disabled` data migration.

## Lifecycle

States: `draft → active ⇄ maintenance`; any state → `disabled`;
`disabled → active`.

- **draft** — configurable and testable; never health-checked, never routed
  to. Activation requires a configured endpoint. A passing connection test is
  recommended but not required (agencies may be temporarily down).
- **active** — routed to and health-checked.
- **maintenance** — health-checked but excluded from routing; UI uses a
  distinct amber "ปิดปรับปรุง" (expected downtime) treatment.
- **disabled** — not checked, not routed; data retained. Muted UI.

Existing `active/inactive` values map to `active/disabled`.

## Health model

Every `active` and `maintenance` agency is periodically checked (all three
connection types; the backend sub-project adds MCP/A2A checks to today's
API-only scheduler). Derived health state rendered by the frontend:

- **up** — last check ok
- **degraded** — ok but recent failures or slow (thresholds defined in the
  backend spec; frontend only renders the state)
- **down** — last check failed
- **unknown** — no checks yet

## API contract

Implemented now as MSW handlers with fixtures; the fixtures are the
executable definition of the contract for sub-project 2.

- `GET /api/v1/agencies` — each agency gains `status` (4-state), `priority`
  (int), `routerHint` (text injected into the LLM router prompt),
  `dispatchTimeoutS`, `rateLimitRpm`, `mcpToolName`, and embedded
  `health: { state, uptime24h, avgLatencyMs24h, lastCheckAt }`
  (`health.state = "unknown"`, numeric fields null for never-checked
  agencies).
- `GET /api/v1/agencies/{id}/health/history?window=24h|7d|30d` — bucketed
  series for charts:
  `[{ bucketStart, uptimePct, avgLatencyMs, checks, failures }]`.
- `PATCH /api/v1/agencies/{id}/status` — body `{ status }`; `422` with a
  message on invalid transitions.
- `POST /api/v1/agencies/mcp/discover` — body `{ endpointUrl }` →
  `{ tools: [{ name, description, inputSchema }] }`. Powers wizard step 2
  before the agency exists.
- `POST /api/v1/agencies` / `PATCH /api/v1/agencies/{id}` — accept the new
  fields; create accepts partial configuration when `status` is `draft`.
- Existing test-connection endpoint unchanged.

## Screens

### Agencies list (`/agencies`)

Card grid of status tiles (evolution of the current cards):

- Tile: logo/name, connection-type badge, lifecycle badge, 24h uptime bar,
  uptime % + avg latency, priority, total calls.
- Draft tiles: dashed/incomplete styling with "ตั้งค่าต่อ →" resuming the
  wizard. Disabled tiles muted. Maintenance tiles amber, still showing
  health.
- Header: filter chips (lifecycle, connection type), search box,
  "เพิ่มหน่วยงาน" navigates to the wizard.
- Per-tile dropdown: test connection (inline result, as today), edit
  (→ detail page), lifecycle quick actions, delete.

### Setup wizard (`/agencies/new`, full page with step sidebar)

1. **ข้อมูลทั่วไป** — name, short name, logo emoji, color, description.
2. **การเชื่อมต่อ** — connection type picker; per-type fields (API:
   endpoint + headers + expected-payload template; MCP: endpoint +
   "Discover tools" listing discovered tools to pick one; A2A: endpoint).
   From this step on, "บันทึก Draft" exits to the detail page with
   `status = draft`.
3. **ทดสอบ** — runs the connection test, shows request/response detail.
   Failure does not block saving Draft.
4. **Routing** — data-scope keyword editor, router hint text, priority,
   timeout/rate-limit overrides.
5. **สรุป** — review; primary "เปิดใช้งาน" (create as Active), secondary
   "บันทึกเป็น Draft".

Editing a Draft re-enters the wizard at the first incomplete step. Editing
non-draft agencies happens inline on detail tabs, never the wizard.

### Detail page (`/agencies/:id`, tabs)

Header: logo, name, lifecycle badge + health dot, สถานะ dropdown offering
only legal transitions (Activate / Maintenance / Disable).

- **ภาพรวม** — stat cards (uptime 24h, avg latency, total calls, rating),
  mini health sparkline, recent activity.
- **Health** — recharts uptime % and latency charts over a selectable
  window (24h / 7d / 30d) from the history endpoint, plus the check log
  table.
- **การเชื่อมต่อ** — endpoint, headers, payload template, MCP tool; inline
  editable with save.
- **Routing** — data-scope editor, router hint, priority, timeout/limits;
  inline editable.
- **Logs** — existing connection-logs tab, kept.

## Frontend architecture

```
features/agencies/
  AgenciesPage.tsx          — filters + tile grid
  AgencyCard.tsx            — status tile (new)
  wizard/
    AgencyWizardPage.tsx    — route, step state, draft-save
    StepGeneral.tsx / StepConnection.tsx / StepTest.tsx /
    StepRouting.tsx / StepReview.tsx
  detail/
    AgencyDetailPage.tsx    — header + lifecycle dropdown + tabs
    OverviewTab.tsx / HealthTab.tsx / ConnectionTab.tsx /
    RoutingTab.tsx / LogsTab.tsx
  useAgencies.ts            — extended hooks (health history, status,
                              discover)
  agencyForm.ts             — validation, extended per step
src/mocks/                  — MSW handlers.ts + fixtures; started only when
                              VITE_USE_MOCKS=true (dev/test)
```

- `AgencyFormDialog`, `AgencyApiFields`, `AgencyHeadersEditor`, and the
  other dialog satellites are deleted — replaced by the wizard and inline
  tab editing. `DeleteAgencyDialog` and `ConnectionTestResult` are kept.
- Types in `shared/types` are extended, not forked.
- Charts use the already-installed `recharts`; MSW is added as a dev
  dependency.

## Error handling

- Mutations keep the existing pattern: Thai-language success/error toasts.
- Invalid lifecycle transition → toast with the 422 message.
- MCP discovery failure → inline error in step 2 with retry; does not block
  saving Draft.
- Health-history fetch failure → chart area shows an error state with
  retry; the rest of the tab still renders.

## Testing

TDD per project rules, vitest as in the existing suite:

- `agencyForm` step-validation unit tests (per-type required fields, draft
  partial-save rules).
- Wizard flow tests with MSW: complete flow per connection type,
  save-as-draft mid-flow, resume-draft at first incomplete step.
- Lifecycle tests: dropdown offers only legal transitions; 422 handled.
- HealthTab: renders charts from history fixture, window switching, error
  state.
- AgencyCard: correct styling per lifecycle state and health state.

## Out of scope (sub-project 2 and beyond)

- All backend changes: model migration, health-check scheduler for MCP/A2A,
  history storage/aggregation, MCP discovery endpoint, router use of
  priority/hint/timeouts, degraded-state thresholds.
- Chat UI, dashboard, analytics surfaces that show agency data.
- Bulk actions on the list page.
