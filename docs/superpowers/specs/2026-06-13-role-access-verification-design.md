# Role Access Verification — Design

Date: 2026-06-13
Status: Approved
Branch: `feat/role-access-verification`

## Goal

Prove that **every role can fully use the pages it is entitled to**, verified at two
independent layers:

1. **API blackbox** — each entitled role reaches each API endpoint its allowed pages
   call. A request that is rejected with **401 or 403** is a failure; any other status
   (including 2xx, 404, 422) means the role got past both authorization gates.
2. **UI e2e** — each role, in a real browser, can open every page it is allowed to see
   without being redirected away, and none of that page's background `/api` calls return
   401/403.

This suite is modeled on the existing blackbox pattern in
`/mnt/c/Users/foo/lucky369/backoffice/blackbox` (TypeScript + Vitest + Axios,
organized by feature with a `scenarios/` folder), extended with a Playwright UI layer.

## Scope

### In scope
- **Positive access only**: confirm entitled roles get through.
- All five roles: `user`, `viewer`, `auditor`, `agency_owner`, `admin`.
- Read / load-time API calls each role's pages make on load.

### Out of scope
- Negative access (roles correctly *blocked*) — already covered by backend pytest
  (`test_role_allowlist.py`, `test_authz.py`, `test_auditor_*.py`).
- Write-action verification for read-only roles (intentionally denied; positive-only).
- Content / visual assertions in the UI layer (render + no-401/403 only).

## Background facts (from codebase exploration)

- **Roles** (least→most privileged): `user`, `viewer`, `auditor`, `agency_owner`,
  `admin`. Defined in `backend/app/schemas/user.py` and `frontend/src/features/auth/roles.ts`.
- **Two-gate authorization**: a request must pass BOTH the global chokepoint
  (`enforce_role_allowlist`, `backend/app/auth/dependencies.py`) AND per-endpoint auth
  (`backend/app/auth/authz.py`). Either gate can reject — which is exactly why the
  positive-access sweep is valuable: a page can be route-allowed yet still have a call
  that 403s at gate 2.
- **Auth**: plain JWT. `POST /api/v1/auth/login` with `{email, password}` returns
  `{access_token, token_type, user}`. The token is sent as `Authorization: Bearer` and
  stored by the frontend in `localStorage.auth_token`.
- **User creation**: `POST /api/v1/users` (admin only) accepts `{email, role,
  display_name, password}`.
- **Admin bootstrap catch-22**: `POST /api/v1/seed/admin` requires an already
  authenticated admin (`require_admin`), so the first admin cannot be created via the
  API on an empty DB. Both suites assume the running instance already has an admin.
- **Frontend served at** `http://localhost:8080` (nginx → frontend/backend); `/api/*`
  proxied to the backend. The e2e `baseURL` and the blackbox `API_URL` come from env.

## Shared foundation — single source of truth

`blackbox/src/access-matrix.ts` encodes the page → endpoint → roles map (derived from
the frontend page components and `roles.ts`) as data, plus the role-account constants.
Both suites import from it:

- The **API suite** iterates the endpoint rows.
- The **e2e suite** iterates the page rows.

Shape:

```ts
export type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface EndpointAccess {
  page: string;        // e.g. "/dashboard"
  method: Method;
  path: string;        // e.g. "/api/v1/dashboard/stats"; {id} placeholders resolved at runtime
  roles: Role[];       // roles entitled to this call
  kind: "read" | "write";
}

export interface PageAccess {
  path: string;        // route, e.g. "/dashboard"
  roles: Role[];       // roles allowed to view the page
}

export const ROLE_ACCOUNTS: Record<Role, { email: string }>; // bb-<role>@example.com
export const ENDPOINT_MATRIX: EndpointAccess[];               // read/load-time entitled calls
export const PAGE_MATRIX: PageAccess[];                        // route → roles (from roles.ts)
```

Only **read / load-time** entitled calls go in `ENDPOINT_MATRIX` for the positive sweep.
Write/mutation endpoints a read-only role is meant to be denied are excluded. Detail
endpoints with `{id}` resolve a real id from the corresponding list endpoint at runtime.

### Derived endpoint matrix (load-time reads)

| Page | Method + Path | Entitled roles |
|------|---------------|----------------|
| /chat | POST /api/v1/chat | all |
| /architecture | GET /api/v1/agencies | all |
| /dashboard | GET /api/v1/dashboard/stats | viewer, auditor, agency_owner, admin |
| /dashboard | GET /api/v1/insight/usage?group_by=model | viewer, auditor, agency_owner, admin |
| /dashboard | GET /api/v1/feedback/stats | viewer, auditor, agency_owner, admin |
| /executive | GET /api/v1/executive-summary | viewer, auditor, agency_owner, admin |
| /health | GET /api/v1/agency-health | viewer, auditor, agency_owner, admin |
| /heatmap | GET /api/v1/usage-heatmap?range=7d | viewer, auditor, agency_owner, admin |
| /usage | GET /api/v1/insight/usage?group_by=api_key | viewer, auditor, admin |
| /feedback | GET /api/v1/feedback/stats | viewer, auditor, admin |
| /agencies | GET /api/v1/agencies | auditor, agency_owner, admin |
| /agencies/:id | GET /api/v1/agencies/{id}/health/history | auditor, agency_owner, admin |
| /agencies/:id | GET /api/v1/feedback/agencies/{id}/low-rated | auditor, agency_owner, admin |
| /history | GET /api/v1/conversations | auditor, agency_owner, admin |
| /connection-logs | GET /api/v1/connection-logs | auditor, agency_owner, admin |
| /connection-logs | GET /api/v1/connection-logs/info | auditor, agency_owner, admin |
| /api-keys | GET /api/v1/api-keys/ | auditor, agency_owner, admin |
| /my-agencies | GET /api/v1/agencies/mine | agency_owner, admin |
| /users | GET /api/v1/users | auditor, admin |
| /audit-log | GET /api/v1/audit-log/ | auditor, admin |
| /settings | GET /api/v1/settings | admin |

Note: `POST /api/v1/chat` is a write but is part of "fully using /chat" for all roles;
under the not-401/403 criterion a stub body returning 400/422 still counts as access
granted. This matrix is the authoritative artifact — it will be refined against the
actual frontend components during implementation.

## Layer 1 — API blackbox (`blackbox/`)

Self-contained TypeScript package mirroring lucky369.

### Tooling
- `vitest`, `axios`, `dotenv`, `typescript`, `@types/node`.
- `package.json` scripts: `test` → `vitest run`, `test:watch` → `vitest`.
- `vitest.config.ts`: `environment: 'node'`, `setupFiles: ['./vitest.setup.ts']`,
  `testTimeout: 30000`, `hookTimeout: 30000`.
- `vitest.setup.ts`: `dotenv` loads `.env.test`.
- `.env.test.example` (committed) and `.env.test` (gitignored):
  `API_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `TEST_USER_PASSWORD`.

### Helpers
- `src/helpers/client.ts` — `createApi(token?)`: axios instance with `baseURL=API_URL`,
  optional `Authorization: Bearer`, and a response interceptor normalizing errors to
  `{ status, data }` (so tests read `err.status` uniformly).
- `src/helpers/auth.ts` — `login(email, password)` → token; `loginAs(role)` → authed
  client for that role's fixture account.
- `src/helpers/provision.ts` — `ensureRoleUsers(adminApi)`: idempotently create one user
  per role (`bb-<role>@example.com`, `TEST_USER_PASSWORD`), tolerating
  already-exists; and `seedDefaults(adminApi)` calling `POST /api/v1/seed/all`. Both run
  once via a Vitest **globalSetup** module.
- `src/helpers/resolve.ts` — `getFirstAgencyId(api)` etc., to fill `{id}` placeholders.

### Specs
- `src/scenarios/role-access.test.ts` — the **matrix sweep**. For each `EndpointAccess`
  row and each entitled role: `loginAs(role)`, call the endpoint, assert
  `expect([401, 403]).not.toContain(status)`.
- Per-feature specs (`src/chat.test.ts`, `dashboard.test.ts`, `agencies.test.ts`,
  `users.test.ts`, `audit.test.ts`, `settings.test.ts`, `connection-logs.test.ts`,
  `history.test.ts`, `api-keys.test.ts`) — exercise each feature's realistic calls with
  proper query params and resolved ids, asserting entitled roles get through.
- `src/auth.test.ts` — login succeeds and returns a token; bad credentials → 401.

## Layer 2 — UI e2e (`e2e/`, Playwright)

Top-level `e2e/` folder.

### Tooling
- `@playwright/test`, `dotenv`, `typescript`.
- `playwright.config.ts`: `baseURL` from env (`E2E_BASE_URL`, default
  `http://localhost:8080`), headless, `trace: 'on-first-retry'`, `globalSetup`.
- `package.json` script: `test` → `playwright test`.

### Global setup (shared provisioning)
- `global-setup.ts` imports `ensureRoleUsers` / `seedDefaults` / `ROLE_ACCOUNTS` from
  `../blackbox/src/...` (relative import — single source of truth for accounts).
- Provisions accounts + seed data once, then for each role logs in via the API and
  writes a per-role Playwright `storageState` with `localStorage.auth_token` set, so
  specs start already authenticated.

### Specs
- `tests/role-pages.spec.ts` — for each role × its allowed pages (from `PAGE_MATRIX`),
  using that role's `storageState`:
  1. attach `page.on('response')` collecting any `/api/...` response with status 401/403;
  2. `page.goto(path)`;
  3. assert the URL did **not** redirect to `/chat` (the route guard allowed it) — except
     for `/chat` and `/architecture` themselves;
  4. assert the collected 401/403 list is empty.

## Auth model summary

`POST /api/v1/auth/login` → `access_token` → `Authorization: Bearer` for API calls; the
UI persists it in `localStorage.auth_token`, which `global-setup` seeds into each role's
`storageState`.

## Prerequisite (catch-22)

`seed_admin` requires an existing admin, so neither suite bootstraps the first admin.
Both assume the running instance already has an admin — default
`admin@example.com` / `admin1234`, or one provided via `.env.test` (`ADMIN_EMAIL` /
`ADMIN_PASSWORD`). Everything else self-provisions from that admin. This is documented in
each suite's README.

## The first run is the audit

Both suites assert intended RBAC. They pass where the two gates truly let an entitled
role through and **fail** where a real gap exists (e.g. the currently-untested assumption
that no auditor-visible page calls `golden-questions` / `eval-results`). Each failure is
triaged as either an application fix or a matrix correction.

## Testing approach

Per project CLAUDE.md (TDD mandatory): for this suite the tests *are* the deliverable.
The discipline applies as: encode each matrix row / spec, run it against the running app,
observe pass/fail, and either fix the app or correct the matrix. The first green run
across all five roles is the success criterion.

## Deliverables checklist

- `blackbox/` package: config, helpers, matrix, scenarios + per-feature specs, README,
  `.env.test.example`.
- `e2e/` package: Playwright config, global setup, `role-pages.spec.ts`, README.
- `.gitignore` entries for `.env.test`, `node_modules`, `playwright-report`,
  `test-results`, `storageState`.
- Optional follow-up (not in initial scope): CI workflow running both suites against a
  spun-up stack.
