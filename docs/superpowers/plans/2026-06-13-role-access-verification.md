# Role Access Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two suites that prove every role can fully reach the API endpoints and UI pages it is entitled to — an API blackbox suite (`blackbox/`) and a Playwright UI e2e suite (`e2e/`).

**Architecture:** A single shared access matrix (`blackbox/src/access-matrix.ts`) encodes page→endpoint→roles plus role-account constants. The API suite logs in per role and asserts each entitled endpoint is not rejected with 401/403. The e2e suite reuses the same accounts/provisioning, logs in each role, visits each allowed page, and asserts no redirect-away and no 401/403 background calls.

**Tech Stack:** TypeScript, Vitest + Axios (API layer), Playwright (UI layer), dotenv. Target app: FastAPI backend behind nginx at `http://localhost:8080`, JWT bearer auth.

**Prerequisite:** A running instance of the app with an admin account already present (default `admin@example.com` / `admin1234`, or set `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `.env.test`). The first admin cannot be bootstrapped via the API (`seed_admin` requires an existing admin).

**Note on DRY:** The matrix sweep (`scenarios/role-access.test.ts`) covers every plain endpoint. Per-feature specs are added only where a call needs special handling (real request body, an `{id}` resolved from a list endpoint) rather than duplicating the sweep for every feature.

---

## File Structure

**`blackbox/`** (API blackbox package)
- `package.json` — deps + scripts
- `tsconfig.json` — TS config
- `vitest.config.ts` — runner config + globalSetup
- `vitest.setup.ts` — loads `.env.test`
- `global-setup.ts` — provisions role users + seed data once
- `.env.test.example` — committed template
- `README.md` — how to run
- `src/access-matrix.ts` — **shared source of truth**: roles, accounts, endpoint + page matrices
- `src/helpers/client.ts` — axios factory
- `src/helpers/auth.ts` — `login`, `loginAs`, `adminApi`
- `src/helpers/provision.ts` — `ensureRoleUsers`, `seedDefaults`
- `src/auth.test.ts` — login smoke
- `src/scenarios/role-access.test.ts` — matrix sweep
- `src/chat.test.ts` — chat POST per role
- `src/agencies.test.ts` — detail endpoints with resolved id

**`e2e/`** (Playwright UI package)
- `package.json` — deps + scripts
- `tsconfig.json`
- `playwright.config.ts`
- `global-setup.ts` — shared provisioning + per-role storageState
- `.env.test.example`
- `README.md`
- `tests/role-pages.spec.ts` — per-role page sweep

**Repo root**
- `.gitignore` — add test artifacts

---

## Task 1: Scaffold the blackbox package

**Files:**
- Create: `blackbox/package.json`
- Create: `blackbox/tsconfig.json`
- Create: `blackbox/vitest.config.ts`
- Create: `blackbox/vitest.setup.ts`
- Create: `blackbox/.env.test.example`
- Modify: `.gitignore`

- [ ] **Step 1: Create `blackbox/package.json`**

```json
{
  "name": "thai-citizen-blackbox",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "axios": "^1.7.0",
    "dotenv": "^16.4.0",
    "typescript": "^5.5.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Create `blackbox/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "types": ["node", "vitest/globals"]
  },
  "include": ["src", "global-setup.ts", "vitest.setup.ts", "vitest.config.ts"]
}
```

- [ ] **Step 3: Create `blackbox/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    globalSetup: ["./global-setup.ts"],
    testTimeout: 30000,
    hookTimeout: 30000,
  },
});
```

- [ ] **Step 4: Create `blackbox/vitest.setup.ts`**

```ts
import { config } from "dotenv";

config({ path: ".env.test" });
```

- [ ] **Step 5: Create `blackbox/.env.test.example`**

```bash
# Base URL of the running app (nginx fronts both UI and /api)
API_URL=http://localhost:8080

# An admin that already exists in the running instance
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=admin1234

# Password assigned to the auto-provisioned bb-<role> test accounts
TEST_USER_PASSWORD=blackbox1234
```

- [ ] **Step 6: Append test artifacts to root `.gitignore`**

Add these lines to `/mnt/c/Users/foo/thai-citizen-guide/.gitignore`:

```
# Test suites
.env.test
blackbox/node_modules
e2e/node_modules
e2e/.auth
playwright-report
test-results
```

- [ ] **Step 7: Install deps and verify vitest runs**

Run: `cd blackbox && pnpm install && pnpm vitest run --reporter=basic`
Expected: vitest starts and reports "No test files found" (no specs yet) — confirms tooling works.

- [ ] **Step 8: Commit**

```bash
rtk git add blackbox/package.json blackbox/tsconfig.json blackbox/vitest.config.ts blackbox/vitest.setup.ts blackbox/.env.test.example .gitignore
rtk git commit -m "chore(blackbox): scaffold API blackbox test package"
```

---

## Task 2: Shared access matrix

**Files:**
- Create: `blackbox/src/access-matrix.ts`

This is pure data + types, imported by both suites. No test of its own; it is exercised by every later task.

- [ ] **Step 1: Create `blackbox/src/access-matrix.ts`**

```ts
export type Role = "user" | "viewer" | "auditor" | "agency_owner" | "admin";

export const ROLES: Role[] = ["user", "viewer", "auditor", "agency_owner", "admin"];

export type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface EndpointAccess {
  page: string;
  method: Method;
  path: string;
  roles: Role[];
  body?: unknown;
}

export interface PageAccess {
  path: string;
  roles: Role[];
}

export const ROLE_ACCOUNTS: Record<Role, { email: string }> = {
  user: { email: "bb-user@example.com" },
  viewer: { email: "bb-viewer@example.com" },
  auditor: { email: "bb-auditor@example.com" },
  agency_owner: { email: "bb-agency-owner@example.com" },
  admin: { email: "bb-admin@example.com" },
};

const ANALYTICS: Role[] = ["viewer", "auditor", "agency_owner", "admin"];
const USAGE_FEEDBACK: Role[] = ["viewer", "auditor", "admin"];
const MANAGEMENT: Role[] = ["auditor", "agency_owner", "admin"];
const OWNER: Role[] = ["agency_owner", "admin"];
const AUDIT: Role[] = ["auditor", "admin"];

// Directly-callable load-time reads each role is entitled to.
// {id}-bearing detail endpoints are handled in agencies.test.ts.
export const ENDPOINT_MATRIX: EndpointAccess[] = [
  { page: "/architecture", method: "GET", path: "/api/v1/agencies", roles: ROLES },

  { page: "/dashboard", method: "GET", path: "/api/v1/dashboard/stats", roles: ANALYTICS },
  { page: "/dashboard", method: "GET", path: "/api/v1/insight/usage?group_by=model", roles: ANALYTICS },
  { page: "/dashboard", method: "GET", path: "/api/v1/feedback/stats", roles: ANALYTICS },
  { page: "/executive", method: "GET", path: "/api/v1/executive-summary", roles: ANALYTICS },
  { page: "/health", method: "GET", path: "/api/v1/agency-health", roles: ANALYTICS },
  { page: "/heatmap", method: "GET", path: "/api/v1/usage-heatmap?range=7d", roles: ANALYTICS },

  { page: "/usage", method: "GET", path: "/api/v1/insight/usage?group_by=api_key", roles: USAGE_FEEDBACK },
  { page: "/feedback", method: "GET", path: "/api/v1/feedback/stats", roles: USAGE_FEEDBACK },

  { page: "/history", method: "GET", path: "/api/v1/conversations", roles: MANAGEMENT },
  { page: "/connection-logs", method: "GET", path: "/api/v1/connection-logs", roles: MANAGEMENT },
  { page: "/connection-logs", method: "GET", path: "/api/v1/connection-logs/info", roles: MANAGEMENT },
  { page: "/api-keys", method: "GET", path: "/api/v1/api-keys/", roles: MANAGEMENT },

  { page: "/my-agencies", method: "GET", path: "/api/v1/agencies/mine", roles: OWNER },

  { page: "/users", method: "GET", path: "/api/v1/users", roles: AUDIT },
  { page: "/audit-log", method: "GET", path: "/api/v1/audit-log/", roles: AUDIT },

  { page: "/settings", method: "GET", path: "/api/v1/settings", roles: ["admin"] },
];

// Route → roles allowed to view (from frontend/src/features/auth/roles.ts).
export const PAGE_MATRIX: PageAccess[] = [
  { path: "/chat", roles: ROLES },
  { path: "/architecture", roles: ROLES },
  { path: "/dashboard", roles: ANALYTICS },
  { path: "/executive", roles: ANALYTICS },
  { path: "/health", roles: ANALYTICS },
  { path: "/heatmap", roles: ANALYTICS },
  { path: "/usage", roles: USAGE_FEEDBACK },
  { path: "/feedback", roles: USAGE_FEEDBACK },
  { path: "/agencies", roles: MANAGEMENT },
  { path: "/history", roles: MANAGEMENT },
  { path: "/connection-logs", roles: MANAGEMENT },
  { path: "/api-keys", roles: MANAGEMENT },
  { path: "/my-agencies", roles: OWNER },
  { path: "/users", roles: AUDIT },
  { path: "/audit-log", roles: AUDIT },
  { path: "/settings", roles: ["admin"] },
];
```

- [ ] **Step 2: Verify it type-checks**

Run: `cd blackbox && pnpm tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
rtk git add blackbox/src/access-matrix.ts
rtk git commit -m "feat(blackbox): shared role access matrix"
```

---

## Task 3: HTTP client + auth helpers

**Files:**
- Create: `blackbox/src/helpers/client.ts`
- Create: `blackbox/src/helpers/auth.ts`
- Test: `blackbox/src/auth.test.ts`

- [ ] **Step 1: Write the failing test `blackbox/src/auth.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { createApi } from "./helpers/client";

describe("auth", () => {
  it("logs in the admin and returns a token", async () => {
    const api = createApi();
    const resp = await api.post("/api/v1/auth/login", {
      email: process.env.ADMIN_EMAIL ?? "admin@example.com",
      password: process.env.ADMIN_PASSWORD ?? "admin1234",
    });
    expect(resp.status).toBe(200);
    expect(typeof resp.data.access_token).toBe("string");
  });

  it("rejects bad credentials with 401", async () => {
    const api = createApi();
    const resp = await api.post("/api/v1/auth/login", {
      email: "nobody@example.com",
      password: "wrong",
    });
    expect(resp.status).toBe(401);
  });
});
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd blackbox && pnpm vitest run src/auth.test.ts`
Expected: FAIL — cannot resolve `./helpers/client` (module not created yet).

- [ ] **Step 3: Create `blackbox/src/helpers/client.ts`**

```ts
import axios, { type AxiosInstance } from "axios";

export const API_URL = (): string => process.env.API_URL ?? "http://localhost:8080";

export function createApi(token?: string): AxiosInstance {
  return axios.create({
    baseURL: API_URL(),
    // Never throw on HTTP status; tests assert on resp.status directly.
    validateStatus: () => true,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}
```

- [ ] **Step 4: Create `blackbox/src/helpers/auth.ts`**

```ts
import type { AxiosInstance } from "axios";
import { createApi } from "./client";
import { ROLE_ACCOUNTS, type Role } from "../access-matrix";

export async function login(email: string, password: string): Promise<string> {
  const resp = await createApi().post("/api/v1/auth/login", { email, password });
  if (resp.status !== 200) {
    throw new Error(`login failed for ${email}: ${resp.status} ${JSON.stringify(resp.data)}`);
  }
  return resp.data.access_token as string;
}

export async function adminApi(): Promise<AxiosInstance> {
  const token = await login(
    process.env.ADMIN_EMAIL ?? "admin@example.com",
    process.env.ADMIN_PASSWORD ?? "admin1234",
  );
  return createApi(token);
}

const tokenCache = new Map<Role, string>();

export async function loginAs(role: Role): Promise<AxiosInstance> {
  let token = tokenCache.get(role);
  if (!token) {
    token = await login(ROLE_ACCOUNTS[role].email, process.env.TEST_USER_PASSWORD ?? "blackbox1234");
    tokenCache.set(role, token);
  }
  return createApi(token);
}
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `cd blackbox && pnpm vitest run src/auth.test.ts`
Expected: PASS (requires the app running with the admin account). Both tests green.

- [ ] **Step 6: Commit**

```bash
rtk git add blackbox/src/helpers/client.ts blackbox/src/helpers/auth.ts blackbox/src/auth.test.ts
rtk git commit -m "feat(blackbox): http client and auth helpers"
```

---

## Task 4: Provisioning + global setup

**Files:**
- Create: `blackbox/src/helpers/provision.ts`
- Create: `blackbox/global-setup.ts`

- [ ] **Step 1: Create `blackbox/src/helpers/provision.ts`**

```ts
import type { AxiosInstance } from "axios";
import { ROLES, ROLE_ACCOUNTS } from "../access-matrix";

// Create one user per role, tolerating accounts that already exist.
export async function ensureRoleUsers(admin: AxiosInstance): Promise<void> {
  const password = process.env.TEST_USER_PASSWORD ?? "blackbox1234";
  for (const role of ROLES) {
    const { email } = ROLE_ACCOUNTS[role];
    const resp = await admin.post("/api/v1/users", {
      email,
      role,
      display_name: `Blackbox ${role}`,
      password,
    });
    // 200/201 created; 400/409 already exists — both acceptable.
    if (![200, 201, 400, 409].includes(resp.status)) {
      throw new Error(`failed to ensure user ${email}: ${resp.status} ${JSON.stringify(resp.data)}`);
    }
  }
}

// Seed default agencies (and admin, which is skipped if present) so reads have data.
export async function seedDefaults(admin: AxiosInstance): Promise<void> {
  await admin.post("/api/v1/seed/all", {});
}
```

- [ ] **Step 2: Create `blackbox/global-setup.ts`**

```ts
import { config } from "dotenv";

config({ path: ".env.test" });

const { adminApi } = await import("./src/helpers/auth");
const { ensureRoleUsers, seedDefaults } = await import("./src/helpers/provision");

export async function setup(): Promise<void> {
  const admin = await adminApi();
  await seedDefaults(admin);
  await ensureRoleUsers(admin);
}
```

Note: the dynamic `import()` after `config()` guarantees env vars are loaded before the
helpers (which read `process.env`) are evaluated.

- [ ] **Step 3: Run the existing auth test to confirm globalSetup provisions without error**

Run: `cd blackbox && pnpm vitest run src/auth.test.ts`
Expected: PASS — globalSetup runs once (seeds + creates the 5 `bb-*` users) and the auth tests still pass. If provisioning fails, the run aborts with the thrown message.

- [ ] **Step 4: Commit**

```bash
rtk git add blackbox/src/helpers/provision.ts blackbox/global-setup.ts
rtk git commit -m "feat(blackbox): role-user provisioning and global setup"
```

---

## Task 5: Matrix sweep scenario

**Files:**
- Create: `blackbox/src/scenarios/role-access.test.ts`

- [ ] **Step 1: Write the test `blackbox/src/scenarios/role-access.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { loginAs } from "../helpers/auth";
import { ENDPOINT_MATRIX, ROLES } from "../access-matrix";

describe("role access matrix (positive)", () => {
  for (const role of ROLES) {
    const entitled = ENDPOINT_MATRIX.filter((e) => e.roles.includes(role));
    for (const e of entitled) {
      it(`${role} may ${e.method} ${e.path}`, async () => {
        const api = await loginAs(role);
        const resp = await api.request({ method: e.method, url: e.path, data: e.body });
        // Only an auth rejection is a failure; 2xx/404/422 mean the role got through.
        expect([401, 403], `${role} blocked from ${e.method} ${e.path}`).not.toContain(resp.status);
      });
    }
  }
});
```

- [ ] **Step 2: Run it**

Run: `cd blackbox && pnpm vitest run src/scenarios/role-access.test.ts`
Expected: All assertions execute. Tests PASS where the two gates let the role through; any FAIL is a real access gap (status 401/403) — record it for triage (app fix vs matrix correction).

- [ ] **Step 3: Triage any failures**

For each failing `role may METHOD path`: inspect `backend/app/auth/dependencies.py`
(chokepoint allowlist) and the endpoint's per-endpoint auth. Decide: is the matrix row
wrong (role shouldn't have that page/call) → fix the matrix; or is it a real backend gap
→ note it in the commit body and open a follow-up. Re-run until green or all failures are
documented as known gaps.

- [ ] **Step 4: Commit**

```bash
rtk git add blackbox/src/scenarios/role-access.test.ts
rtk git commit -m "test(blackbox): positive role access matrix sweep"
```

---

## Task 6: Feature specs needing special handling

**Files:**
- Create: `blackbox/src/chat.test.ts`
- Create: `blackbox/src/agencies.test.ts`

- [ ] **Step 1: Write `blackbox/src/chat.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { loginAs } from "./helpers/auth";
import { ROLES } from "./access-matrix";

describe("chat access (all roles)", () => {
  for (const role of ROLES) {
    it(`${role} may POST /api/v1/chat`, async () => {
      const api = await loginAs(role);
      const resp = await api.post("/api/v1/chat", { message: "blackbox ping" });
      // A stub body may yield 400/422; only 401/403 means the role was denied access.
      expect([401, 403], `${role} blocked from chat`).not.toContain(resp.status);
    });
  }
});
```

- [ ] **Step 2: Write `blackbox/src/agencies.test.ts`**

```ts
import { describe, it, expect, beforeAll } from "vitest";
import { loginAs } from "./helpers/auth";
import type { Role } from "./access-matrix";

const ENTITLED: Role[] = ["auditor", "agency_owner", "admin"];

describe("agency detail endpoints (positive)", () => {
  let agencyId: string | undefined;

  beforeAll(async () => {
    const api = await loginAs("admin");
    const resp = await api.get("/api/v1/agencies");
    expect(resp.status).toBe(200);
    const list = Array.isArray(resp.data) ? resp.data : resp.data.data;
    agencyId = list?.[0]?.id;
    expect(agencyId, "need at least one seeded agency").toBeTruthy();
  });

  for (const role of ENTITLED) {
    it(`${role} may GET agency health history`, async () => {
      const api = await loginAs(role);
      const resp = await api.get(`/api/v1/agencies/${agencyId}/health/history`);
      expect([401, 403], `${role} blocked from health history`).not.toContain(resp.status);
    });

    it(`${role} may GET agency low-rated feedback`, async () => {
      const api = await loginAs(role);
      const resp = await api.get(`/api/v1/feedback/agencies/${agencyId}/low-rated`);
      expect([401, 403], `${role} blocked from low-rated feedback`).not.toContain(resp.status);
    });
  }
});
```

- [ ] **Step 3: Run both specs**

Run: `cd blackbox && pnpm vitest run src/chat.test.ts src/agencies.test.ts`
Expected: PASS, or document any 401/403 gap (e.g. `agency_owner` ownership requirement on
detail endpoints) per Task 5 Step 3.

- [ ] **Step 4: Run the full suite**

Run: `cd blackbox && pnpm test`
Expected: every spec runs; green except documented known gaps.

- [ ] **Step 5: Commit**

```bash
rtk git add blackbox/src/chat.test.ts blackbox/src/agencies.test.ts
rtk git commit -m "test(blackbox): chat and agency detail access specs"
```

---

## Task 7: Blackbox README

**Files:**
- Create: `blackbox/README.md`

- [ ] **Step 1: Create `blackbox/README.md`**

```markdown
# Blackbox API tests

Positive role-access checks against a running instance: every role can reach the API
endpoints its allowed pages call. A request is a failure only if rejected with 401/403.

## Prerequisite

The target instance must already have an admin account. The first admin cannot be
created via the API. Default expected admin: `admin@example.com` / `admin1234`.

## Setup

    cp .env.test.example .env.test   # edit if your URL/admin differ
    pnpm install

## Run

    pnpm test          # one-shot
    pnpm test:watch    # watch mode

`global-setup.ts` runs once: seeds default agencies and creates one `bb-<role>` user per
role (idempotent). The matrix lives in `src/access-matrix.ts` and is shared with the e2e
suite.
```

- [ ] **Step 2: Commit**

```bash
rtk git add blackbox/README.md
rtk git commit -m "docs(blackbox): usage readme"
```

---

## Task 8: Scaffold the e2e package

**Files:**
- Create: `e2e/package.json`
- Create: `e2e/tsconfig.json`
- Create: `e2e/playwright.config.ts`
- Create: `e2e/.env.test.example`

- [ ] **Step 1: Create `e2e/package.json`**

axios is included because the e2e global setup imports the blackbox auth/provision helpers, which depend on it.

```json
{
  "name": "thai-citizen-e2e",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "playwright test"
  },
  "devDependencies": {
    "@playwright/test": "^1.47.0",
    "@types/node": "^22.0.0",
    "axios": "^1.7.0",
    "dotenv": "^16.4.0",
    "typescript": "^5.5.0"
  }
}
```

- [ ] **Step 2: Create `e2e/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "types": ["node"]
  },
  "include": ["tests", "global-setup.ts", "playwright.config.ts"]
}
```

- [ ] **Step 3: Create `e2e/playwright.config.ts`**

```ts
import { defineConfig } from "@playwright/test";
import { config } from "dotenv";

config({ path: ".env.test" });

export default defineConfig({
  testDir: "./tests",
  globalSetup: "./global-setup.ts",
  timeout: 30000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "on-first-retry",
  },
});
```

- [ ] **Step 4: Create `e2e/.env.test.example`**

```bash
# Running app URL (UI + /api behind nginx)
E2E_BASE_URL=http://localhost:8080
API_URL=http://localhost:8080

# Existing admin in the running instance
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=admin1234

# Password for the auto-provisioned bb-<role> accounts (must match blackbox/.env.test)
TEST_USER_PASSWORD=blackbox1234
```

- [ ] **Step 5: Install Playwright + browser**

Run: `cd e2e && pnpm install && pnpm playwright install chromium`
Expected: deps installed, chromium downloaded.

- [ ] **Step 6: Commit**

```bash
rtk git add e2e/package.json e2e/tsconfig.json e2e/playwright.config.ts e2e/.env.test.example
rtk git commit -m "chore(e2e): scaffold playwright package"
```

---

## Task 9: e2e global setup (shared provisioning + storageState)

**Files:**
- Create: `e2e/global-setup.ts`

- [ ] **Step 1: Create `e2e/global-setup.ts`**

```ts
import { config } from "dotenv";

config({ path: ".env.test" });

import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const { adminApi, login } = await import("../blackbox/src/helpers/auth");
const { ensureRoleUsers, seedDefaults } = await import("../blackbox/src/helpers/provision");
const { ROLES, ROLE_ACCOUNTS } = await import("../blackbox/src/access-matrix");

export default async function globalSetup(): Promise<void> {
  const admin = await adminApi();
  await seedDefaults(admin);
  await ensureRoleUsers(admin);

  mkdirSync(".auth", { recursive: true });
  const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:8080";
  const password = process.env.TEST_USER_PASSWORD ?? "blackbox1234";

  for (const role of ROLES) {
    const token = await login(ROLE_ACCOUNTS[role].email, password);
    const browser = await chromium.launch();
    const ctx = await browser.newContext({ baseURL });
    const page = await ctx.newPage();
    await page.addInitScript((t) => {
      window.localStorage.setItem("auth_token", t as string);
    }, token);
    await page.goto(baseURL);
    await ctx.storageState({ path: `.auth/${role}.json` });
    await browser.close();
  }
}
```

- [ ] **Step 2: Type-check**

Run: `cd e2e && pnpm tsc --noEmit`
Expected: no errors (cross-package import of blackbox helpers resolves).

- [ ] **Step 3: Commit**

```bash
rtk git add e2e/global-setup.ts
rtk git commit -m "feat(e2e): shared provisioning and per-role storage state"
```

---

## Task 10: Per-role page sweep spec

**Files:**
- Create: `e2e/tests/role-pages.spec.ts`

- [ ] **Step 1: Write `e2e/tests/role-pages.spec.ts`**

```ts
import { test, expect } from "@playwright/test";
import { ROLES, PAGE_MATRIX } from "../../blackbox/src/access-matrix";

// Pages every authenticated role may see; visiting them is never a redirect failure.
const ALWAYS_ALLOWED = new Set(["/chat", "/architecture"]);

for (const role of ROLES) {
  const pages = PAGE_MATRIX.filter((p) => p.roles.includes(role));

  test.describe(`${role} page access`, () => {
    test.use({ storageState: `.auth/${role}.json` });

    for (const p of pages) {
      test(`${role} can open ${p.path}`, async ({ page }) => {
        const denied: string[] = [];
        page.on("response", (resp) => {
          if (resp.url().includes("/api/") && [401, 403].includes(resp.status())) {
            denied.push(`${resp.status()} ${resp.url()}`);
          }
        });

        await page.goto(p.path);
        await page.waitForLoadState("networkidle");

        // Guard must not bounce an entitled role back to /chat.
        if (!ALWAYS_ALLOWED.has(p.path)) {
          expect(page.url(), `${role} was redirected away from ${p.path}`).not.toMatch(/\/chat(\?|$)/);
        }

        expect(denied, `401/403 calls on ${p.path}:\n${denied.join("\n")}`).toHaveLength(0);
      });
    }
  });
}
```

- [ ] **Step 2: Run the e2e suite**

Run: `cd e2e && pnpm test`
Expected: For each role × allowed page, the page opens without redirect-away and with no
401/403 background calls. Failures surface real UI-level access gaps — triage as in Task 5
Step 3 (matrix correction vs backend/frontend fix).

- [ ] **Step 3: Commit**

```bash
rtk git add e2e/tests/role-pages.spec.ts
rtk git commit -m "test(e2e): per-role page access sweep"
```

---

## Task 11: e2e README

**Files:**
- Create: `e2e/README.md`

- [ ] **Step 1: Create `e2e/README.md`**

```markdown
# UI e2e tests (Playwright)

Drives the real frontend as each role: visits every page the role is allowed to see and
asserts (a) it is not redirected away and (b) no background `/api` call returns 401/403.

## Prerequisite

A running instance with an existing admin (see ../blackbox/README.md). Browser:
`pnpm playwright install chromium`.

## Setup

    cp .env.test.example .env.test   # edit if URL/admin differ
    pnpm install

## Run

    pnpm test

`global-setup.ts` reuses the blackbox provisioning helpers (same `bb-<role>` accounts and
access matrix), logs in each role, and saves a `.auth/<role>.json` storage state used by
the specs.
```

- [ ] **Step 2: Commit**

```bash
rtk git add e2e/README.md
rtk git commit -m "docs(e2e): usage readme"
```

---

## Task 12: Full run + PR

- [ ] **Step 1: Run both suites end to end**

Run: `cd blackbox && pnpm test && cd ../e2e && pnpm test`
Expected: both green, except any access gaps documented during triage.

- [ ] **Step 2: Push and open a PR into `dev`**

Per project CLAUDE.md, branch off into `dev` (never push to `main` directly).

```bash
rtk git push -u origin feat/role-access-verification
rtk gh pr create --base dev --title "test: role access verification (API blackbox + UI e2e)" --body "Adds blackbox/ (Vitest+Axios) and e2e/ (Playwright) suites verifying every role can fully reach the endpoints and pages it is entitled to. Shared access matrix in blackbox/src/access-matrix.ts. See docs/superpowers/specs/2026-06-13-role-access-verification-design.md."
```

---

## Self-Review notes

- **Spec coverage:** shared matrix (Task 2), API client/auth (Task 3), provisioning incl.
  catch-22 prereq (Task 4, READMEs), matrix sweep (Task 5), feature specs for
  chat/agency-detail (Task 6), e2e config/setup/spec (Tasks 8–10), READMEs (7, 11),
  gitignore (Task 1). The "first run is the audit" behavior is realized by the triage
  steps (Task 5/6/10 Step "triage").
- **Positive-only:** all assertions use `not.toContain([401,403])` and never assert a role
  IS blocked — matches scope.
- **Type consistency:** `Role`, `ROLES`, `ROLE_ACCOUNTS`, `ENDPOINT_MATRIX`, `PAGE_MATRIX`,
  `login`, `loginAs`, `adminApi`, `ensureRoleUsers`, `seedDefaults` are defined in Tasks
  2–4 and used with the same names/signatures in Tasks 5–10.
- **Known deviation from spec file list (documented in plan header):** per-feature specs
  limited to chat + agencies (special handling) instead of one file per feature, since the
  matrix sweep already covers plain GETs (DRY).
```
