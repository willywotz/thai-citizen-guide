# Agency Management Redesign — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild agency management as status-tile list + full-page setup wizard + tabbed detail page, with a 4-state lifecycle, health monitoring UI, and routing controls, running against MSW mock handlers that define the backend contract.

**Architecture:** Frontend-first (spec: `docs/superpowers/specs/2026-06-11-agency-management-redesign-frontend-design.md`). New types and lifecycle rules go into shared modules; MSW handlers + fixtures are the executable API contract; the agencies feature splits into `wizard/` and `detail/` subdirectories. Old dialog-based components are deleted at the end.

**Tech Stack:** React 18 + TypeScript, react-router 6, TanStack Query 5, axios, shadcn/radix UI, recharts (installed), MSW v2 (to install), vitest + testing-library.

**Conventions for every task:**
- Work happens in `/mnt/c/Users/foo/thai-citizen-guide/frontend` (branch `feat/agency-redesign-frontend`, already created).
- Wire format is snake_case (matches existing backend); frontend types are camelCase mapped in `mapRowToAgency`.
- Run single test files with `pnpm vitest run <path>`; full suite `pnpm test`; lint `pnpm lint`.
- All user-facing strings follow the existing style: Thai with English technical terms.
- Prefix all commands with `rtk` per project rules (e.g. `rtk pnpm vitest run …`).

---

### Task 1: Extend agency types for the new contract

**Files:**
- Modify: `frontend/src/shared/types/agency.ts`
- Modify: `frontend/src/features/agencies/agencyForm.ts:17` (status type)
- Modify: `frontend/src/features/agencies/agencyForm.test.ts:47,128` (status literals)
- Modify: `frontend/src/features/agencies/AgencyFormDialog.tsx:43,216,220` (status literals; file dies in Task 15 but must compile until then)
- Test: `frontend/src/shared/types/agency.test.ts` (new)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/shared/types/agency.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { mapRowToAgency, type AgencyRow } from "./agency";

const baseRow: AgencyRow = {
  id: "a1",
  name: "กรมสรรพากร",
  short_name: "RD",
  logo: "🏛️",
  connection_type: "API",
  status: "active",
  description: "ภาษีอากร",
  data_scope: ["ภาษี"],
  total_calls: 10,
  color: "hsl(213 70% 45%)",
  endpoint_url: "https://rd.example/chat",
  api_key_name: null,
  auth_method: "api_key",
  auth_header: "",
  base_path: "",
  rate_limit_rpm: null,
  request_format: "json",
  api_endpoints: [],
  response_schema: [],
  api_spec_raw: null,
  expected_payload: null,
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z",
  api_headers: [],
};

describe("mapRowToAgency", () => {
  it("maps new contract fields", () => {
    const agency = mapRowToAgency({
      ...baseRow,
      priority: 1,
      router_hint: "คำถามภาษีเงินได้",
      dispatch_timeout_s: 30,
      mcp_tool_name: "chat_with_rd",
      rating_up: 5,
      rating_down: 1,
      health: {
        state: "up",
        uptime_24h: 99.2,
        avg_latency_ms_24h: 320,
        last_check_at: "2026-06-11T08:00:00Z",
      },
    });
    expect(agency.priority).toBe(1);
    expect(agency.routerHint).toBe("คำถามภาษีเงินได้");
    expect(agency.dispatchTimeoutS).toBe(30);
    expect(agency.mcpToolName).toBe("chat_with_rd");
    expect(agency.ratingUp).toBe(5);
    expect(agency.ratingDown).toBe(1);
    expect(agency.health).toEqual({
      state: "up",
      uptime24h: 99.2,
      avgLatencyMs24h: 320,
      lastCheckAt: "2026-06-11T08:00:00Z",
    });
  });

  it("defaults health to unknown and new fields to null/empty when absent", () => {
    const agency = mapRowToAgency(baseRow);
    expect(agency.health).toEqual({
      state: "unknown",
      uptime24h: null,
      avgLatencyMs24h: null,
      lastCheckAt: null,
    });
    expect(agency.priority).toBeNull();
    expect(agency.routerHint).toBe("");
    expect(agency.dispatchTimeoutS).toBeNull();
    expect(agency.mcpToolName).toBeNull();
    expect(agency.ratingUp).toBe(0);
    expect(agency.ratingDown).toBe(0);
  });

  it("normalizes legacy and unknown statuses to disabled", () => {
    expect(mapRowToAgency({ ...baseRow, status: "inactive" }).status).toBe("disabled");
    expect(mapRowToAgency({ ...baseRow, status: "garbage" }).status).toBe("disabled");
    expect(mapRowToAgency({ ...baseRow, status: "maintenance" }).status).toBe("maintenance");
    expect(mapRowToAgency({ ...baseRow, status: "draft" }).status).toBe("draft");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/shared/types/agency.test.ts`
Expected: FAIL — `priority` etc. do not exist on the mapped object / TS errors.

- [ ] **Step 3: Implement the type changes**

In `frontend/src/shared/types/agency.ts`, add after the `ResponseField` interface:

```ts
export const LIFECYCLE_STATUSES = ["draft", "active", "maintenance", "disabled"] as const;
export type AgencyLifecycleStatus = (typeof LIFECYCLE_STATUSES)[number];

export type HealthState = "up" | "degraded" | "down" | "unknown";

export interface AgencyHealth {
  state: HealthState;
  uptime24h: number | null;
  avgLatencyMs24h: number | null;
  lastCheckAt: string | null;
}

export const UNKNOWN_HEALTH: AgencyHealth = {
  state: "unknown",
  uptime24h: null,
  avgLatencyMs24h: null,
  lastCheckAt: null,
};

export type HealthWindow = "24h" | "7d" | "30d";

export interface HealthHistoryBucket {
  bucketStart: string;
  uptimePct: number;
  avgLatencyMs: number;
  checks: number;
  failures: number;
}

// snake_case wire shape of one history bucket
export interface HealthHistoryBucketRow {
  bucket_start: string;
  uptime_pct: number;
  avg_latency_ms: number;
  checks: number;
  failures: number;
}

export function mapBucketRow(row: HealthHistoryBucketRow): HealthHistoryBucket {
  return {
    bucketStart: row.bucket_start,
    uptimePct: row.uptime_pct,
    avgLatencyMs: row.avg_latency_ms,
    checks: row.checks,
    failures: row.failures,
  };
}

export interface McpTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export function normalizeStatus(raw: string): AgencyLifecycleStatus {
  return (LIFECYCLE_STATUSES as readonly string[]).includes(raw)
    ? (raw as AgencyLifecycleStatus)
    : "disabled";
}
```

In the `Agency` interface, replace `status: 'active' | 'inactive';` with `status: AgencyLifecycleStatus;` and add before `createdAt`:

```ts
  priority: number | null;
  routerHint: string;
  dispatchTimeoutS: number | null;
  mcpToolName: string | null;
  ratingUp: number;
  ratingDown: number;
  health: AgencyHealth;
```

In `AgencyRow`, add (all optional — the live backend does not send them yet):

```ts
  priority?: number | null;
  router_hint?: string | null;
  dispatch_timeout_s?: number | null;
  mcp_tool_name?: string | null;
  rating_up?: number;
  rating_down?: number;
  health?: {
    state: HealthState;
    uptime_24h: number | null;
    avg_latency_ms_24h: number | null;
    last_check_at: string | null;
  } | null;
```

In `mapRowToAgency`, replace `status: row.status as Agency['status'],` with `status: normalizeStatus(row.status),` and add to the returned object:

```ts
    priority: row.priority ?? null,
    routerHint: row.router_hint ?? "",
    dispatchTimeoutS: row.dispatch_timeout_s ?? null,
    mcpToolName: row.mcp_tool_name ?? null,
    ratingUp: row.rating_up ?? 0,
    ratingDown: row.rating_down ?? 0,
    health: row.health
      ? {
          state: row.health.state,
          uptime24h: row.health.uptime_24h,
          avgLatencyMs24h: row.health.avg_latency_ms_24h,
          lastCheckAt: row.health.last_check_at,
        }
      : UNKNOWN_HEALTH,
```

- [ ] **Step 4: Fix the three compile ripples**

1. `agencyForm.ts:17` — change `status: "active" | "inactive";` to `status: AgencyLifecycleStatus;` and add `AgencyLifecycleStatus` to the type import from `@/shared/types/agency`. In `DEFAULT_FORM_STATE` change `status: "active"` to `status: "draft"`.
2. `agencyForm.test.ts` — change the `status: "inactive"` fixture value (line 47) and the `expect(s.status).toBe("inactive")` assertion (line 128) to `"disabled"`. If any other test asserts the default status is `"active"`, update it to `"draft"`.
3. `AgencyFormDialog.tsx` — change `useState<"active" | "inactive">("active")` to `useState<"active" | "disabled">("active")`, the `onValueChange` cast to `"active" | "disabled"`, and `<SelectItem value="inactive">Inactive</SelectItem>` to `<SelectItem value="disabled">Disabled</SelectItem>`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/shared/types/agency.test.ts src/features/agencies/agencyForm.test.ts`
Expected: PASS (both files).

- [ ] **Step 6: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/shared/types/agency.ts frontend/src/shared/types/agency.test.ts frontend/src/features/agencies/agencyForm.ts frontend/src/features/agencies/agencyForm.test.ts frontend/src/features/agencies/AgencyFormDialog.tsx
rtk git commit -m "feat(agencies): extend types with lifecycle, health, and routing fields"
```

---

### Task 2: Lifecycle transition module

**Files:**
- Create: `frontend/src/features/agencies/lifecycle.ts`
- Test: `frontend/src/features/agencies/lifecycle.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/lifecycle.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { isLegalTransition, legalTransitions, STATUS_LABEL } from "./lifecycle";

describe("legalTransitions", () => {
  it("draft can activate or be disabled", () => {
    expect(legalTransitions("draft")).toEqual(["active", "disabled"]);
  });
  it("active can go to maintenance or disabled", () => {
    expect(legalTransitions("active")).toEqual(["maintenance", "disabled"]);
  });
  it("maintenance can go back to active or be disabled", () => {
    expect(legalTransitions("maintenance")).toEqual(["active", "disabled"]);
  });
  it("disabled can only be re-activated", () => {
    expect(legalTransitions("disabled")).toEqual(["active"]);
  });
});

describe("isLegalTransition", () => {
  it("accepts legal and rejects illegal transitions", () => {
    expect(isLegalTransition("draft", "active")).toBe(true);
    expect(isLegalTransition("disabled", "maintenance")).toBe(false);
    expect(isLegalTransition("active", "draft")).toBe(false);
  });
});

describe("STATUS_LABEL", () => {
  it("has a label for every status", () => {
    expect(STATUS_LABEL.draft).toBeTruthy();
    expect(STATUS_LABEL.active).toBeTruthy();
    expect(STATUS_LABEL.maintenance).toBeTruthy();
    expect(STATUS_LABEL.disabled).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/lifecycle.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/features/agencies/lifecycle.ts`:

```ts
import type { AgencyLifecycleStatus, HealthState } from "@/shared/types/agency";

export const LEGAL_TRANSITIONS: Record<AgencyLifecycleStatus, AgencyLifecycleStatus[]> = {
  draft: ["active", "disabled"],
  active: ["maintenance", "disabled"],
  maintenance: ["active", "disabled"],
  disabled: ["active"],
};

export function legalTransitions(from: AgencyLifecycleStatus): AgencyLifecycleStatus[] {
  return LEGAL_TRANSITIONS[from];
}

export function isLegalTransition(
  from: AgencyLifecycleStatus,
  to: AgencyLifecycleStatus,
): boolean {
  return LEGAL_TRANSITIONS[from].includes(to);
}

export const STATUS_LABEL: Record<AgencyLifecycleStatus, string> = {
  draft: "Draft",
  active: "Active",
  maintenance: "ปิดปรับปรุง",
  disabled: "Disabled",
};

export const STATUS_BADGE_CLASS: Record<AgencyLifecycleStatus, string> = {
  draft: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  active: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  maintenance: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  disabled: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
};

export const TRANSITION_LABEL: Record<AgencyLifecycleStatus, string> = {
  draft: "กลับเป็น Draft",
  active: "เปิดใช้งาน",
  maintenance: "ปิดปรับปรุง",
  disabled: "ปิดการใช้งาน",
};

export const HEALTH_DOT_CLASS: Record<HealthState, string> = {
  up: "bg-green-500",
  degraded: "bg-amber-500",
  down: "bg-red-500",
  unknown: "bg-gray-300",
};

export const HEALTH_LABEL: Record<HealthState, string> = {
  up: "ปกติ",
  degraded: "เสื่อมประสิทธิภาพ",
  down: "ล่ม",
  unknown: "ยังไม่มีข้อมูล",
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/lifecycle.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/lifecycle.ts frontend/src/features/agencies/lifecycle.test.ts
rtk git commit -m "feat(agencies): add lifecycle transition rules and display maps"
```

---

### Task 3: MSW mock layer (the executable contract)

**Files:**
- Create: `frontend/src/mocks/fixtures.ts`
- Create: `frontend/src/mocks/handlers.ts`
- Create: `frontend/src/mocks/browser.ts`
- Create: `frontend/src/mocks/server.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/package.json` (msw dev dep, added by install)
- Test: `frontend/src/mocks/handlers.test.ts`

- [ ] **Step 1: Install MSW and generate the service worker**

```bash
cd frontend && rtk pnpm add -D msw && rtk pnpm dlx msw init public/ --save
```

Expected: `msw` in devDependencies, `frontend/public/mockServiceWorker.js` created, `"msw": { "workerDirectory": ["public"] }` added to package.json.

- [ ] **Step 2: Write the failing handler test**

Create `frontend/src/mocks/handlers.test.ts`:

```ts
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { resetMockData } from "./fixtures";
import { server } from "./server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  resetMockData();
});
afterAll(() => server.close());

const BASE = "http://localhost:3000";

describe("agency mock handlers", () => {
  it("GET /api/v1/agencies returns fixtures with embedded health", async () => {
    const res = await fetch(`${BASE}/api/v1/agencies`);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.total).toBeGreaterThanOrEqual(5);
    const active = body.data.find((a: { status: string }) => a.status === "active");
    expect(active.health.state).toBeDefined();
    expect(active.health.uptime_24h).not.toBeNull();
  });

  it("GET health/history returns buckets for a window", async () => {
    const list = await (await fetch(`${BASE}/api/v1/agencies`)).json();
    const id = list.data[0].id;
    const res = await fetch(`${BASE}/api/v1/agencies/${id}/health/history?window=24h`);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.data.length).toBe(24);
    expect(body.data[0]).toHaveProperty("bucket_start");
    expect(body.data[0]).toHaveProperty("uptime_pct");
    expect(body.data[0]).toHaveProperty("avg_latency_ms");
  });

  it("PATCH status applies a legal transition and rejects an illegal one with 422", async () => {
    const list = await (await fetch(`${BASE}/api/v1/agencies`)).json();
    const active = list.data.find((a: { status: string }) => a.status === "active");

    const ok = await fetch(`${BASE}/api/v1/agencies/${active.id}/status`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ status: "maintenance" }),
    });
    expect(ok.status).toBe(200);
    expect((await ok.json()).status).toBe("maintenance");

    const bad = await fetch(`${BASE}/api/v1/agencies/${active.id}/status`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ status: "draft" }),
    });
    expect(bad.status).toBe(422);
    expect((await bad.json()).detail).toContain("transition");
  });

  it("POST mcp/discover returns tools", async () => {
    const res = await fetch(`${BASE}/api/v1/agencies/mcp/discover`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ endpoint_url: "https://mcp.example/sse" }),
    });
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.tools.length).toBeGreaterThan(0);
    expect(body.tools[0]).toHaveProperty("name");
    expect(body.tools[0]).toHaveProperty("input_schema");
  });

  it("POST /api/v1/agencies creates a draft with partial config", async () => {
    const res = await fetch(`${BASE}/api/v1/agencies`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name: "กรมใหม่", short_name: "NEW", status: "draft" }),
    });
    const body = await res.json();
    expect(res.status).toBe(201);
    expect(body.id).toBeTruthy();
    expect(body.status).toBe("draft");
    expect(body.health).toBeNull();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/mocks/handlers.test.ts`
Expected: FAIL — modules not found.

- [ ] **Step 4: Implement fixtures**

Create `frontend/src/mocks/fixtures.ts`:

```ts
import type { AgencyRow, HealthHistoryBucketRow, HealthWindow } from "@/shared/types/agency";

function row(partial: Partial<AgencyRow> & Pick<AgencyRow, "id" | "name" | "short_name">): AgencyRow {
  return {
    logo: "🏢",
    connection_type: "API",
    status: "active",
    description: "",
    data_scope: [],
    total_calls: 0,
    color: "hsl(213 70% 45%)",
    endpoint_url: "",
    api_key_name: null,
    auth_method: "api_key",
    auth_header: "",
    base_path: "",
    rate_limit_rpm: null,
    request_format: "json",
    api_endpoints: [],
    response_schema: [],
    api_spec_raw: null,
    expected_payload: null,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
    api_headers: [],
    priority: null,
    router_hint: "",
    dispatch_timeout_s: null,
    mcp_tool_name: null,
    rating_up: 0,
    rating_down: 0,
    health: null,
    ...partial,
  };
}

export function makeFixtureAgencies(): AgencyRow[] {
  return [
    row({
      id: "11111111-1111-1111-1111-111111111111",
      name: "กรมสรรพากร",
      short_name: "RD",
      logo: "🏛️",
      connection_type: "API",
      status: "active",
      description: "ข้อมูลภาษีอากร",
      data_scope: ["ภาษี", "ภาษีเงินได้"],
      total_calls: 1204,
      endpoint_url: "https://rd.example/api/chat",
      expected_payload: { query: "__query__", session_id: "__session_id__" },
      priority: 1,
      router_hint: "คำถามเกี่ยวกับภาษีทุกประเภท",
      dispatch_timeout_s: 30,
      rating_up: 41,
      rating_down: 3,
      health: { state: "up", uptime_24h: 99.2, avg_latency_ms_24h: 320, last_check_at: "2026-06-11T08:00:00Z" },
    }),
    row({
      id: "22222222-2222-2222-2222-222222222222",
      name: "สำนักงานคณะกรรมการอาหารและยา",
      short_name: "อย.",
      logo: "💊",
      connection_type: "MCP",
      status: "active",
      description: "ข้อมูลอาหารและยา",
      data_scope: ["ยา", "อาหาร", "เครื่องสำอาง"],
      total_calls: 458,
      endpoint_url: "https://fda.example/mcp",
      mcp_tool_name: "chat_with_fda",
      priority: 2,
      health: { state: "degraded", uptime_24h: 71.0, avg_latency_ms_24h: 1230, last_check_at: "2026-06-11T08:00:00Z" },
    }),
    row({
      id: "33333333-3333-3333-3333-333333333333",
      name: "กรมที่ดิน",
      short_name: "DOL",
      logo: "🗂️",
      connection_type: "A2A",
      status: "draft",
      description: "ข้อมูลโฉนดที่ดิน",
    }),
    row({
      id: "44444444-4444-4444-4444-444444444444",
      name: "กรมการปกครอง",
      short_name: "DOPA",
      logo: "🪪",
      connection_type: "API",
      status: "disabled",
      description: "ข้อมูลทะเบียนราษฎร",
      endpoint_url: "https://dopa.example/api/chat",
    }),
    row({
      id: "55555555-5555-5555-5555-555555555555",
      name: "กรมขนส่งทางบก",
      short_name: "DLT",
      logo: "🚗",
      connection_type: "API",
      status: "maintenance",
      description: "ข้อมูลใบขับขี่และทะเบียนรถ",
      data_scope: ["ใบขับขี่", "ทะเบียนรถ"],
      endpoint_url: "https://dlt.example/api/chat",
      priority: 3,
      health: { state: "down", uptime_24h: 12.5, avg_latency_ms_24h: 2100, last_check_at: "2026-06-11T07:30:00Z" },
    }),
  ];
}

/** Mutable in-memory store the handlers operate on. */
export let mockAgencies: AgencyRow[] = makeFixtureAgencies();

export function resetMockData(): void {
  mockAgencies = makeFixtureAgencies();
}

export const FIXTURE_MCP_TOOLS = [
  { name: "chat_with_fda", description: "ถามตอบข้อมูล อย.", input_schema: { type: "object", properties: { query: { type: "string" } } } },
  { name: "search_products", description: "ค้นหาผลิตภัณฑ์", input_schema: { type: "object", properties: { keyword: { type: "string" } } } },
];

const WINDOW_BUCKETS: Record<HealthWindow, { count: number; stepMs: number }> = {
  "24h": { count: 24, stepMs: 3_600_000 },
  "7d": { count: 7 * 24, stepMs: 3_600_000 },
  "30d": { count: 30, stepMs: 86_400_000 },
};

export function makeHistory(agencyId: string, window: HealthWindow): HealthHistoryBucketRow[] {
  const { count, stepMs } = WINDOW_BUCKETS[window];
  const end = Date.now();
  // Deterministic pseudo-random per agency so charts look real but stable.
  const seed = agencyId.charCodeAt(0) + agencyId.charCodeAt(2);
  return Array.from({ length: count }, (_, i) => {
    const wave = Math.abs(Math.sin((i + seed) / 5));
    const failures = wave > 0.93 ? 2 : wave > 0.85 ? 1 : 0;
    const checks = 12;
    return {
      bucket_start: new Date(end - (count - i) * stepMs).toISOString(),
      uptime_pct: Math.round(((checks - failures) / checks) * 1000) / 10,
      avg_latency_ms: Math.round(250 + wave * 900),
      checks,
      failures,
    };
  });
}
```

- [ ] **Step 5: Implement handlers**

Create `frontend/src/mocks/handlers.ts`:

```ts
import { http, HttpResponse } from "msw";

import { LEGAL_TRANSITIONS } from "@/features/agencies/lifecycle";
import type { AgencyLifecycleStatus, AgencyRow, HealthWindow } from "@/shared/types/agency";

import { FIXTURE_MCP_TOOLS, makeHistory, mockAgencies } from "./fixtures";

function findAgency(id: string | readonly string[]): AgencyRow | undefined {
  return mockAgencies.find((a) => a.id === id);
}

export const handlers = [
  http.get("*/api/v1/agencies", () =>
    HttpResponse.json({ data: mockAgencies, total: mockAgencies.length }),
  ),

  http.get("*/api/v1/agencies/:id/health/history", ({ params, request }) => {
    const agency = findAgency(params.id as string);
    if (!agency) return HttpResponse.json({ detail: "Agency not found" }, { status: 404 });
    const url = new URL(request.url);
    const window = (url.searchParams.get("window") ?? "24h") as HealthWindow;
    return HttpResponse.json({ data: makeHistory(agency.id, window) });
  }),

  http.patch("*/api/v1/agencies/:id/status", async ({ params, request }) => {
    const agency = findAgency(params.id as string);
    if (!agency) return HttpResponse.json({ detail: "Agency not found" }, { status: 404 });
    const body = (await request.json()) as { status: AgencyLifecycleStatus };
    const from = agency.status as AgencyLifecycleStatus;
    if (!LEGAL_TRANSITIONS[from]?.includes(body.status)) {
      return HttpResponse.json(
        { detail: `Illegal transition: ${from} → ${body.status}` },
        { status: 422 },
      );
    }
    agency.status = body.status;
    return HttpResponse.json(agency);
  }),

  http.post("*/api/v1/agencies/mcp/discover", async ({ request }) => {
    const body = (await request.json()) as { endpoint_url?: string };
    if (!body.endpoint_url) {
      return HttpResponse.json({ detail: "endpoint_url is required" }, { status: 422 });
    }
    return HttpResponse.json({ tools: FIXTURE_MCP_TOOLS });
  }),

  http.post("*/api/v1/agencies", async ({ request }) => {
    const body = (await request.json()) as Partial<AgencyRow>;
    const created: AgencyRow = {
      ...mockAgencies[0],
      api_endpoints: [],
      response_schema: [],
      api_headers: [],
      data_scope: [],
      expected_payload: null,
      total_calls: 0,
      rating_up: 0,
      rating_down: 0,
      priority: null,
      router_hint: "",
      dispatch_timeout_s: null,
      mcp_tool_name: null,
      endpoint_url: "",
      description: "",
      health: null,
      ...body,
      id: crypto.randomUUID(),
      status: body.status ?? "draft",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    mockAgencies.push(created);
    return HttpResponse.json(created, { status: 201 });
  }),

  http.patch("*/api/v1/agencies/:id", async ({ params, request }) => {
    const agency = findAgency(params.id as string);
    if (!agency) return HttpResponse.json({ detail: "Agency not found" }, { status: 404 });
    const body = (await request.json()) as Partial<AgencyRow>;
    Object.assign(agency, body, { updated_at: new Date().toISOString() });
    return HttpResponse.json(agency);
  }),

  http.delete("*/api/v1/agencies/:id", ({ params }) => {
    const idx = mockAgencies.findIndex((a) => a.id === params.id);
    if (idx === -1) return HttpResponse.json({ detail: "Agency not found" }, { status: 404 });
    mockAgencies.splice(idx, 1);
    return HttpResponse.json({ success: true });
  }),

  http.get("*/api/v1/agencies/:id/test", ({ params }) => {
    const agency = findAgency(params.id as string);
    if (!agency) return HttpResponse.json({ detail: "Agency not found" }, { status: 404 });
    return HttpResponse.json({
      success: true,
      protocol: agency.connection_type,
      version: "1.0",
      steps: [
        { name: "DNS lookup", status: "ok", detail: agency.endpoint_url },
        { name: "Handshake", status: "ok", detail: "200 OK" },
      ],
      latency: "320ms",
    });
  }),
];
```

Note: the wildcard `*/api/v1/...` patterns match any origin so the same handlers work in jsdom tests and the dev browser.

- [ ] **Step 6: Implement browser worker, node server, and main.tsx gate**

Create `frontend/src/mocks/browser.ts`:

```ts
import { setupWorker } from "msw/browser";

import { handlers } from "./handlers";

export const worker = setupWorker(...handlers);
```

Create `frontend/src/mocks/server.ts`:

```ts
import { setupServer } from "msw/node";

import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

Replace the contents of `frontend/src/main.tsx` (current content renders `<App />` directly) with:

```tsx
import { createRoot } from "react-dom/client";

import App from "./App.tsx";
import "./index.css";

async function enableMocking(): Promise<void> {
  if (import.meta.env.VITE_USE_MOCKS !== "true") return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass" });
}

enableMocking().then(() => {
  createRoot(document.getElementById("root")!).render(<App />);
});
```

(Read `main.tsx` first and keep any existing imports it has.) `onUnhandledRequest: "bypass"` means auth/chat keep hitting the real backend; only the agency contract is mocked.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/mocks/handlers.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 8: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/mocks frontend/src/main.tsx frontend/public/mockServiceWorker.js frontend/package.json frontend/pnpm-lock.yaml
rtk git commit -m "feat(agencies): add MSW mock layer defining the new API contract"
```

---

### Task 4: New data hooks (health history, status transition, MCP discovery)

**Files:**
- Modify: `frontend/src/features/agencies/useAgencies.ts`
- Test: `frontend/src/features/agencies/useAgencies.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/useAgencies.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { resetMockData } from "@/mocks/fixtures";
import { server } from "@/mocks/server";

import {
  useAgencies,
  useDiscoverMcpTools,
  useHealthHistory,
  useUpdateAgencyStatus,
} from "./useAgencies";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  resetMockData();
});
afterAll(() => server.close());

const ACTIVE_ID = "11111111-1111-1111-1111-111111111111";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("useAgencies", () => {
  it("returns mapped agencies with health", async () => {
    const { result } = renderHook(() => useAgencies(), { wrapper });
    await waitFor(() => expect(result.current.data?.length).toBeGreaterThan(0));
    const active = result.current.data!.find((a) => a.id === ACTIVE_ID)!;
    expect(active.health.state).toBe("up");
    expect(active.routerHint).toContain("ภาษี");
  });
});

describe("useHealthHistory", () => {
  it("fetches camelCase buckets for a window", async () => {
    const { result } = renderHook(() => useHealthHistory(ACTIVE_ID, "24h"), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data!.length).toBe(24);
    expect(result.current.data![0].uptimePct).toBeTypeOf("number");
    expect(result.current.data![0].bucketStart).toBeTypeOf("string");
  });

  it("does not fetch without an id", () => {
    const { result } = renderHook(() => useHealthHistory(undefined, "24h"), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
  });
});

describe("useUpdateAgencyStatus", () => {
  it("applies a legal transition", async () => {
    const { result } = renderHook(() => useUpdateAgencyStatus(), { wrapper });
    const updated = await result.current.mutateAsync({ id: ACTIVE_ID, status: "maintenance" });
    expect(updated.status).toBe("maintenance");
  });

  it("surfaces the 422 detail on an illegal transition", async () => {
    const { result } = renderHook(() => useUpdateAgencyStatus(), { wrapper });
    await expect(
      result.current.mutateAsync({ id: ACTIVE_ID, status: "draft" }),
    ).rejects.toThrow(/transition/i);
  });
});

describe("useDiscoverMcpTools", () => {
  it("returns mapped tools", async () => {
    const { result } = renderHook(() => useDiscoverMcpTools(), { wrapper });
    const tools = await result.current.mutateAsync({ endpointUrl: "https://mcp.example/sse" });
    expect(tools[0].name).toBe("chat_with_fda");
    expect(tools[0].inputSchema).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/useAgencies.test.tsx`
Expected: FAIL — `useHealthHistory` etc. not exported.

- [ ] **Step 3: Implement the new hooks**

In `frontend/src/features/agencies/useAgencies.ts`:

1. Extend the type imports:

```ts
import type {
  AgencyLifecycleStatus,
  AgencyRow,
  HealthHistoryBucket,
  HealthHistoryBucketRow,
  HealthWindow,
  McpTool,
} from "@/shared/types/agency";
import { mapBucketRow, mapRowToAgency } from "@/shared/types/agency";
```

2. In `useCreateAgency` and `useUpdateAgency`, add to the posted body (snake_case):

```ts
        priority: agency.priority,
        router_hint: agency.routerHint,
        dispatch_timeout_s: agency.dispatchTimeoutS,
        mcp_tool_name: agency.mcpToolName,
```

3. Change `useCreateAgency`'s `mutationFn` to return the mapped created agency (the wizard needs the new id):

```ts
    mutationFn: async (agency: Partial<Agency>) => {
      const row = await api.post<AgencyRow>('/api/v1/agencies', {
        // ...existing + new snake_case fields as above
      });
      return mapRowToAgency(row);
    },
```

4. Append the three new hooks at the end of the file:

```ts
export function useHealthHistory(agencyId: string | undefined, window: HealthWindow) {
  return useQuery({
    queryKey: ['agency-health-history', agencyId, window],
    queryFn: async (): Promise<HealthHistoryBucket[]> => {
      const res = await api.get<{ data: HealthHistoryBucketRow[] }>(
        `/api/v1/agencies/${agencyId}/health/history`,
        { window },
      );
      return res.data.map(mapBucketRow);
    },
    enabled: Boolean(agencyId),
  });
}

export function useUpdateAgencyStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: AgencyLifecycleStatus }) => {
      const row = await api.patch<AgencyRow>(`/api/v1/agencies/${id}/status`, { status });
      return mapRowToAgency(row);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agencies'] }),
  });
}

interface McpToolRow {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export function useDiscoverMcpTools() {
  return useMutation({
    mutationFn: async ({ endpointUrl }: { endpointUrl: string }): Promise<McpTool[]> => {
      const res = await api.post<{ tools: McpToolRow[] }>('/api/v1/agencies/mcp/discover', {
        endpoint_url: endpointUrl,
      });
      return res.tools.map((t) => ({
        name: t.name,
        description: t.description,
        inputSchema: t.input_schema,
      }));
    },
  });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/useAgencies.test.tsx`
Expected: PASS (6 tests).

- [ ] **Step 5: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/useAgencies.ts frontend/src/features/agencies/useAgencies.test.tsx
rtk git commit -m "feat(agencies): add health-history, status, and MCP-discovery hooks"
```

---

### Task 5: Wizard form model — validation, payload, resume logic

**Files:**
- Modify: `frontend/src/features/agencies/agencyForm.ts`
- Modify: `frontend/src/features/agencies/agencyForm.test.ts` (append new describe blocks)

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/features/agencies/agencyForm.test.ts`:

```ts
import {
  canActivate,
  firstIncompleteStep,
  isStepConnectionValid,
  isStepGeneralValid,
  WIZARD_STEPS,
} from "./agencyForm";

describe("wizard step validation", () => {
  it("defines five steps in order", () => {
    expect(WIZARD_STEPS.map((s) => s.id)).toEqual([
      "general",
      "connection",
      "test",
      "routing",
      "review",
    ]);
  });

  it("general step requires name and shortName", () => {
    expect(isStepGeneralValid({ ...DEFAULT_FORM_STATE })).toBe(false);
    expect(isStepGeneralValid({ ...DEFAULT_FORM_STATE, name: "กรมที่ดิน", shortName: "DOL" })).toBe(true);
  });

  it("connection step requires endpoint; MCP also requires a selected tool", () => {
    const api = { ...DEFAULT_FORM_STATE, connectionType: "API" as const };
    expect(isStepConnectionValid(api)).toBe(false);
    expect(isStepConnectionValid({ ...api, endpointUrl: "https://x.example" })).toBe(true);

    const mcp = { ...DEFAULT_FORM_STATE, connectionType: "MCP" as const, endpointUrl: "https://x.example/mcp" };
    expect(isStepConnectionValid(mcp)).toBe(false);
    expect(isStepConnectionValid({ ...mcp, mcpToolName: "chat" })).toBe(true);
  });

  it("canActivate requires general + connection", () => {
    expect(canActivate(DEFAULT_FORM_STATE)).toBe(false);
    expect(
      canActivate({
        ...DEFAULT_FORM_STATE,
        name: "กรมที่ดิน",
        shortName: "DOL",
        endpointUrl: "https://x.example",
      }),
    ).toBe(true);
  });

  it("firstIncompleteStep walks general → connection → test", () => {
    expect(firstIncompleteStep(DEFAULT_FORM_STATE)).toBe("general");
    expect(firstIncompleteStep({ ...DEFAULT_FORM_STATE, name: "ก", shortName: "ข" })).toBe("connection");
    expect(
      firstIncompleteStep({ ...DEFAULT_FORM_STATE, name: "ก", shortName: "ข", endpointUrl: "https://x.example" }),
    ).toBe("test");
  });
});

describe("buildSavePayload routing fields", () => {
  it("includes routing fields and parses numerics", () => {
    const payload = buildSavePayload(
      {
        ...DEFAULT_FORM_STATE,
        name: "ก",
        shortName: "ข",
        priority: "2",
        routerHint: "ภาษี",
        dispatchTimeoutS: "45",
        mcpToolName: "chat",
        connectionType: "MCP",
        endpointUrl: "https://x.example/mcp",
      },
      null,
    );
    expect(payload.priority).toBe(2);
    expect(payload.routerHint).toBe("ภาษี");
    expect(payload.dispatchTimeoutS).toBe(45);
    expect(payload.mcpToolName).toBe("chat");
  });

  it("maps empty numeric inputs to null", () => {
    const payload = buildSavePayload({ ...DEFAULT_FORM_STATE, name: "ก", shortName: "ข" }, null);
    expect(payload.priority).toBeNull();
    expect(payload.dispatchTimeoutS).toBeNull();
  });
});
```

(`DEFAULT_FORM_STATE` and `buildSavePayload` are already imported at the top of the test file; merge imports rather than duplicating.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/agencyForm.test.ts`
Expected: FAIL — new exports missing.

- [ ] **Step 3: Implement**

In `frontend/src/features/agencies/agencyForm.ts`:

1. Extend `AgencyFormState` with:

```ts
  // Routing
  priority: string;
  routerHint: string;
  dispatchTimeoutS: string;
  // MCP
  mcpToolName: string;
```

2. Extend `DEFAULT_FORM_STATE` with:

```ts
  priority: "",
  routerHint: "",
  dispatchTimeoutS: "",
  mcpToolName: "",
```

3. Extend `agencyToFormState` with:

```ts
    priority: agency.priority != null ? String(agency.priority) : "",
    routerHint: agency.routerHint ?? "",
    dispatchTimeoutS: agency.dispatchTimeoutS != null ? String(agency.dispatchTimeoutS) : "",
    mcpToolName: agency.mcpToolName ?? "",
```

4. Add the wizard model (after `isFormValid`, which stays for now):

```ts
export type WizardStepId = "general" | "connection" | "test" | "routing" | "review";

export const WIZARD_STEPS: { id: WizardStepId; label: string }[] = [
  { id: "general", label: "ข้อมูลทั่วไป" },
  { id: "connection", label: "การเชื่อมต่อ" },
  { id: "test", label: "ทดสอบ" },
  { id: "routing", label: "Routing" },
  { id: "review", label: "สรุป" },
];

export function isStepGeneralValid(s: Pick<AgencyFormState, "name" | "shortName">): boolean {
  return Boolean(s.name.trim() && s.shortName.trim());
}

export function isStepConnectionValid(
  s: Pick<AgencyFormState, "connectionType" | "endpointUrl" | "mcpToolName">,
): boolean {
  if (!s.endpointUrl.trim()) return false;
  if (s.connectionType === "MCP") return Boolean(s.mcpToolName.trim());
  return true;
}

export function canActivate(s: AgencyFormState): boolean {
  return isStepGeneralValid(s) && isStepConnectionValid(s);
}

export function firstIncompleteStep(s: AgencyFormState): WizardStepId {
  if (!isStepGeneralValid(s)) return "general";
  if (!isStepConnectionValid(s)) return "connection";
  return "test";
}

function parseIntOrNull(raw: string): number | null {
  const n = raw.trim() ? parseInt(raw, 10) : NaN;
  return Number.isNaN(n) ? null : n;
}
```

5. In `buildSavePayload`, add to `base`:

```ts
    priority: parseIntOrNull(state.priority),
    routerHint: state.routerHint,
    dispatchTimeoutS: parseIntOrNull(state.dispatchTimeoutS),
    mcpToolName: state.connectionType === "MCP" ? state.mcpToolName || null : null,
```

Also replace the existing `rateLimitRpm` IIFE in the API branch with `rateLimitRpm: parseIntOrNull(state.rateLimitRpm),` (same behavior, reuses the helper).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/agencyForm.test.ts`
Expected: PASS (all old + new tests).

- [ ] **Step 5: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/agencyForm.ts frontend/src/features/agencies/agencyForm.test.ts
rtk git commit -m "feat(agencies): add wizard step model and routing fields to form state"
```

---

### Task 6: AgencyCard status tile

**Files:**
- Create: `frontend/src/features/agencies/AgencyCard.tsx`
- Test: `frontend/src/features/agencies/AgencyCard.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/AgencyCard.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { mapRowToAgency } from "@/shared/types/agency";
import { makeFixtureAgencies } from "@/mocks/fixtures";

import { AgencyCard } from "./AgencyCard";

const agencies = makeFixtureAgencies().map(mapRowToAgency);
const active = agencies.find((a) => a.status === "active")!;
const draft = agencies.find((a) => a.status === "draft")!;
const disabled = agencies.find((a) => a.status === "disabled")!;
const maintenance = agencies.find((a) => a.status === "maintenance")!;

const noop = vi.fn();

function renderCard(agency: typeof active) {
  return render(
    <MemoryRouter>
      <AgencyCard agency={agency} onTest={noop} onDelete={noop} onStatusChange={noop} testing={false} testResult={null} />
    </MemoryRouter>,
  );
}

describe("AgencyCard", () => {
  it("shows health stats for an active agency", () => {
    renderCard(active);
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText(/99.2%/)).toBeInTheDocument();
    expect(screen.getByText(/320\s*ms/)).toBeInTheDocument();
    expect(screen.getByText(/P1/)).toBeInTheDocument();
  });

  it("shows a continue-setup link for a draft", () => {
    renderCard(draft);
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ตั้งค่าต่อ/ })).toHaveAttribute(
      "href",
      `/agencies/${draft.id}/setup`,
    );
    expect(screen.queryByText(/uptime/i)).not.toBeInTheDocument();
  });

  it("mutes a disabled agency and hides health", () => {
    const { container } = renderCard(disabled);
    expect(screen.getByText("Disabled")).toBeInTheDocument();
    expect(container.firstElementChild?.className).toContain("opacity-60");
  });

  it("marks maintenance with the expected-downtime badge but keeps health", () => {
    renderCard(maintenance);
    expect(screen.getByText("ปิดปรับปรุง")).toBeInTheDocument();
    expect(screen.getByText(/12.5%/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/AgencyCard.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/features/agencies/AgencyCard.tsx`:

```tsx
import { ArrowRight, MoreVertical, Pencil, Trash2, Wifi } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import type { Agency, AgencyLifecycleStatus } from "@/shared/types/agency";

import { ConnectionTestResult, type TestResult } from "./ConnectionTestResult";
import {
  HEALTH_DOT_CLASS,
  legalTransitions,
  STATUS_BADGE_CLASS,
  STATUS_LABEL,
  TRANSITION_LABEL,
} from "./lifecycle";

const connectionTypeColors: Record<string, string> = {
  MCP: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  API: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  A2A: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

interface Props {
  agency: Agency;
  onTest: (agency: Agency) => void;
  onDelete: (agency: Agency) => void;
  onStatusChange: (agency: Agency, status: AgencyLifecycleStatus) => void;
  testing: boolean;
  testResult: TestResult | null;
}

export function AgencyCard({ agency, onTest, onDelete, onStatusChange, testing, testResult }: Props) {
  const navigate = useNavigate();
  const showHealth = agency.status === "active" || agency.status === "maintenance";
  const uptime = agency.health.uptime24h;

  return (
    <Card
      className={`overflow-hidden cursor-pointer hover:shadow-md transition-shadow ${
        agency.status === "disabled" ? "opacity-60" : ""
      } ${agency.status === "draft" ? "border-dashed" : ""} ${
        agency.status === "maintenance" ? "border-amber-300 dark:border-amber-700" : ""
      }`}
      onClick={() => navigate(`/agencies/${agency.id}`)}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
              style={{ backgroundColor: `${agency.color}15` }}
            >
              {agency.logo}
            </div>
            <div>
              <CardTitle className="text-sm flex items-center gap-1.5">
                {agency.name}
                {showHealth && (
                  <span className={`inline-block w-2 h-2 rounded-full ${HEALTH_DOT_CLASS[agency.health.state]}`} />
                )}
              </CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">{agency.description}</p>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={(e) => e.stopPropagation()}>
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); navigate(`/agencies/${agency.id}`); }}>
                <Pencil className="h-3.5 w-3.5 mr-2" /> แก้ไข
              </DropdownMenuItem>
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onTest(agency); }}>
                <Wifi className="h-3.5 w-3.5 mr-2" /> ทดสอบการเชื่อมต่อ
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {legalTransitions(agency.status).map((to) => (
                <DropdownMenuItem key={to} onClick={(e) => { e.stopPropagation(); onStatusChange(agency, to); }}>
                  {TRANSITION_LABEL[to]}
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={(e) => { e.stopPropagation(); onDelete(agency); }}
                className="text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5 mr-2" /> ลบ
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Badge className={`text-[10px] ${connectionTypeColors[agency.connectionType] || ""}`}>
            {agency.connectionType}
          </Badge>
          <Badge className={`text-[10px] ${STATUS_BADGE_CLASS[agency.status]}`}>
            {STATUS_LABEL[agency.status]}
          </Badge>
          {agency.priority != null && (
            <Badge variant="outline" className="text-[10px]">P{agency.priority}</Badge>
          )}
        </div>

        {showHealth && (
          <div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  agency.health.state === "up"
                    ? "bg-green-500"
                    : agency.health.state === "degraded"
                      ? "bg-amber-500"
                      : "bg-red-500"
                }`}
                style={{ width: `${uptime ?? 0}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
              <span>uptime 24h · {uptime != null ? `${uptime}%` : "—"}</span>
              <span>
                {agency.health.avgLatencyMs24h != null ? `${agency.health.avgLatencyMs24h} ms` : "—"}
              </span>
            </div>
          </div>
        )}

        {agency.status === "draft" && (
          <Link
            to={`/agencies/${agency.id}/setup`}
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            ตั้งค่าต่อ <ArrowRight className="h-3 w-3" />
          </Link>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-border">
          <span className="text-xs text-muted-foreground">จำนวนครั้งที่เรียกใช้</span>
          <span className="text-sm font-semibold text-foreground">{agency.totalCalls.toLocaleString()}</span>
        </div>

        {(testing || testResult) && <ConnectionTestResult result={testResult} loading={testing} />}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/AgencyCard.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/AgencyCard.tsx frontend/src/features/agencies/AgencyCard.test.tsx
rtk git commit -m "feat(agencies): add AgencyCard status tile"
```

---

### Task 7: Redesigned AgenciesPage (filters + tiles, wizard entry)

**Files:**
- Modify: `frontend/src/features/agencies/AgenciesPage.tsx` (full rewrite)
- Test: `frontend/src/features/agencies/AgenciesPage.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/AgenciesPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { resetMockData } from "@/mocks/fixtures";
import { server } from "@/mocks/server";

import AgenciesPage from "./AgenciesPage";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  resetMockData();
});
afterAll(() => server.close());

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/agencies"]}>
        <AgenciesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AgenciesPage", () => {
  it("renders all fixture agencies as tiles", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("กรมสรรพากร")).toBeInTheDocument());
    expect(screen.getByText("กรมที่ดิน")).toBeInTheDocument();
    expect(screen.getByText("กรมขนส่งทางบก")).toBeInTheDocument();
  });

  it("filters by lifecycle state", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("กรมสรรพากร")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Draft" }));
    expect(screen.getByText("กรมที่ดิน")).toBeInTheDocument();
    expect(screen.queryByText("กรมสรรพากร")).not.toBeInTheDocument();
  });

  it("filters by search text", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("กรมสรรพากร")).toBeInTheDocument());
    await userEvent.type(screen.getByPlaceholderText(/ค้นหา/), "ขนส่ง");
    expect(screen.getByText("กรมขนส่งทางบก")).toBeInTheDocument();
    expect(screen.queryByText("กรมสรรพากร")).not.toBeInTheDocument();
  });

  it("links the add button to the wizard", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("กรมสรรพากร")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /เพิ่มหน่วยงาน/ })).toHaveAttribute("href", "/agencies/new");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/AgenciesPage.test.tsx`
Expected: FAIL (no filters/search/link yet).

- [ ] **Step 3: Rewrite the page**

Replace the contents of `frontend/src/features/agencies/AgenciesPage.tsx` with:

```tsx
import { Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import type { Agency, AgencyLifecycleStatus } from "@/shared/types/agency";

import { AgencyCard } from "./AgencyCard";
import type { TestResult } from "./ConnectionTestResult";
import { DeleteAgencyDialog } from "./DeleteAgencyDialog";
import { STATUS_LABEL } from "./lifecycle";
import {
  useAgencies,
  useDeleteAgency,
  useTestConnection,
  useUpdateAgencyStatus,
} from "./useAgencies";

type StatusFilter = AgencyLifecycleStatus | "all";
type TypeFilter = Agency["connectionType"] | "all";

const STATUS_FILTERS: StatusFilter[] = ["all", "active", "draft", "maintenance", "disabled"];
const TYPE_FILTERS: TypeFilter[] = ["all", "API", "MCP", "A2A"];

export default function AgenciesPage() {
  const { data: agencies = [], isLoading } = useAgencies();
  const deleteMutation = useDeleteAgency();
  const testMutation = useTestConnection();
  const statusMutation = useUpdateAgencyStatus();

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [search, setSearch] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Agency | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult | null>>({});

  const filtered = useMemo(
    () =>
      agencies.filter((a) => {
        if (statusFilter !== "all" && a.status !== statusFilter) return false;
        if (typeFilter !== "all" && a.connectionType !== typeFilter) return false;
        const q = search.trim().toLowerCase();
        if (q && !`${a.name} ${a.shortName} ${a.description}`.toLowerCase().includes(q)) return false;
        return true;
      }),
    [agencies, statusFilter, typeFilter, search],
  );

  const handleTest = async (agency: Agency) => {
    setTestingId(agency.id);
    setTestResults((prev) => ({ ...prev, [agency.id]: null }));
    try {
      const result = await testMutation.mutateAsync({ agencyId: agency.id });
      setTestResults((prev) => ({ ...prev, [agency.id]: result }));
    } catch {
      setTestResults((prev) => ({ ...prev, [agency.id]: { success: false, error: "Connection failed" } }));
    } finally {
      setTestingId(null);
    }
  };

  const handleStatusChange = async (agency: Agency, status: AgencyLifecycleStatus) => {
    try {
      await statusMutation.mutateAsync({ id: agency.id, status });
      toast.success(`เปลี่ยนสถานะเป็น ${STATUS_LABEL[status]} สำเร็จ`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
      toast.success("ลบหน่วยงานสำเร็จ");
      setDeleteTarget(null);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
    }
  };

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">จัดการหน่วยงานที่เชื่อมต่อ</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            รองรับ MCP, A2A และ API สำหรับการสื่อสารระหว่าง AI Agent
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">{filtered.length} หน่วยงาน</span>
          <Button size="sm" asChild>
            <Link to="/agencies/new">
              <Plus className="h-4 w-4 mr-1" /> เพิ่มหน่วยงาน
            </Link>
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {STATUS_FILTERS.map((s) => (
          <Button
            key={s}
            size="sm"
            variant={statusFilter === s ? "default" : "outline"}
            onClick={() => setStatusFilter(s)}
          >
            {s === "all" ? "ทั้งหมด" : STATUS_LABEL[s]}
          </Button>
        ))}
        <span className="mx-1 h-4 w-px bg-border" />
        {TYPE_FILTERS.map((t) => (
          <Button
            key={t}
            size="sm"
            variant={typeFilter === t ? "default" : "outline"}
            onClick={() => setTypeFilter(t)}
          >
            {t === "all" ? "ทุกประเภท" : t}
          </Button>
        ))}
        <Input
          placeholder="ค้นหาหน่วยงาน…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-8 w-48 ml-auto"
        />
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">กำลังโหลด...</div>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {filtered.map((agency) => (
            <AgencyCard
              key={agency.id}
              agency={agency}
              onTest={handleTest}
              onDelete={setDeleteTarget}
              onStatusChange={handleStatusChange}
              testing={testingId === agency.id}
              testResult={testResults[agency.id] ?? null}
            />
          ))}
        </div>
      )}

      <DeleteAgencyDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        agencyName={deleteTarget?.name || ""}
        onConfirm={handleDelete}
        deleting={deleteMutation.isPending}
      />
    </div>
  );
}
```

(`AgencyFormDialog` import and create/edit dialog wiring are gone — creation now goes through the wizard, editing through the detail page.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/AgenciesPage.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/AgenciesPage.tsx frontend/src/features/agencies/AgenciesPage.test.tsx
rtk git commit -m "feat(agencies): redesign list page with status tiles and filters"
```

---

### Task 8: Wizard scaffold + StepGeneral + routes

**Files:**
- Create: `frontend/src/features/agencies/wizard/AgencyWizardPage.tsx`
- Create: `frontend/src/features/agencies/wizard/StepGeneral.tsx`
- Modify: `frontend/src/App.tsx` (routes)
- Test: `frontend/src/features/agencies/wizard/AgencyWizardPage.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/wizard/AgencyWizardPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { resetMockData } from "@/mocks/fixtures";
import { server } from "@/mocks/server";

import AgencyWizardPage from "./AgencyWizardPage";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  resetMockData();
});
afterAll(() => server.close());

export function renderWizard(initialEntry = "/agencies/new") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/agencies/new" element={<AgencyWizardPage />} />
          <Route path="/agencies/:id/setup" element={<AgencyWizardPage />} />
          <Route path="/agencies/:id" element={<div>detail-page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AgencyWizardPage scaffold", () => {
  it("renders the five-step sidebar starting on ข้อมูลทั่วไป", () => {
    renderWizard();
    expect(screen.getByText("ข้อมูลทั่วไป")).toBeInTheDocument();
    expect(screen.getByText("การเชื่อมต่อ")).toBeInTheDocument();
    expect(screen.getByText("สรุป")).toBeInTheDocument();
    expect(screen.getByLabelText("ชื่อหน่วยงาน")).toBeInTheDocument();
  });

  it("blocks ถัดไป until general step is valid", async () => {
    renderWizard();
    expect(screen.getByRole("button", { name: /ถัดไป/ })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("ชื่อหน่วยงาน"), "กรมทดสอบ");
    await userEvent.type(screen.getByLabelText("ชื่อย่อ"), "TST");
    expect(screen.getByRole("button", { name: /ถัดไป/ })).toBeEnabled();
  });

  it("resumes a draft at its first incomplete step", async () => {
    // Fixture draft 333… has name+shortName but no endpoint → connection step.
    renderWizard("/agencies/33333333-3333-3333-3333-333333333333/setup");
    await waitFor(() => expect(screen.getByLabelText("Endpoint URL")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/wizard/AgencyWizardPage.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement StepGeneral**

Create `frontend/src/features/agencies/wizard/StepGeneral.tsx`:

```tsx
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";

import type { AgencyFormState } from "../agencyForm";

interface Props {
  form: AgencyFormState;
  patch: (p: Partial<AgencyFormState>) => void;
}

export function StepGeneral({ form, patch }: Props) {
  return (
    <div className="space-y-4 max-w-lg">
      <div className="space-y-1.5">
        <Label htmlFor="wiz-name">ชื่อหน่วยงาน</Label>
        <Input id="wiz-name" value={form.name} onChange={(e) => patch({ name: e.target.value })} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="wiz-short">ชื่อย่อ</Label>
        <Input id="wiz-short" value={form.shortName} onChange={(e) => patch({ shortName: e.target.value })} />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="wiz-logo">โลโก้ (emoji)</Label>
          <Input id="wiz-logo" value={form.logo} onChange={(e) => patch({ logo: e.target.value })} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wiz-color">สี</Label>
          <Input id="wiz-color" value={form.color} onChange={(e) => patch({ color: e.target.value })} />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="wiz-desc">คำอธิบาย</Label>
        <Textarea id="wiz-desc" rows={3} value={form.description} onChange={(e) => patch({ description: e.target.value })} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement the wizard page**

Create `frontend/src/features/agencies/wizard/AgencyWizardPage.tsx`. Steps `connection`, `test`, `routing`, `review` render placeholders for now (replaced in Tasks 9–11 — the placeholder must include an `Endpoint URL`-labeled input for the connection step so the resume test passes; the real StepConnection replaces it in Task 9):

```tsx
import { ArrowLeft, Check } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";

import {
  agencyToFormState,
  buildSavePayload,
  DEFAULT_FORM_STATE,
  firstIncompleteStep,
  isStepConnectionValid,
  isStepGeneralValid,
  parseExpectedPayload,
  WIZARD_STEPS,
  type AgencyFormState,
  type WizardStepId,
} from "../agencyForm";
import { useAgencies, useCreateAgency, useUpdateAgency } from "../useAgencies";
import { StepGeneral } from "./StepGeneral";

function stepIndex(id: WizardStepId): number {
  return WIZARD_STEPS.findIndex((s) => s.id === id);
}

export default function AgencyWizardPage() {
  const { id: routeId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: agencies = [], isLoading } = useAgencies();
  const createMutation = useCreateAgency();
  const updateMutation = useUpdateAgency();

  const [form, setForm] = useState<AgencyFormState>(DEFAULT_FORM_STATE);
  const [step, setStep] = useState<WizardStepId>("general");
  const [agencyId, setAgencyId] = useState<string | null>(routeId ?? null);
  const [loaded, setLoaded] = useState(false);

  // Resume mode: hydrate form from the existing draft, jump to first incomplete step.
  useEffect(() => {
    if (!routeId || loaded || isLoading) return;
    const agency = agencies.find((a) => a.id === routeId);
    if (agency) {
      const state = agencyToFormState(agency);
      setForm(state);
      setStep(firstIncompleteStep(state));
      setLoaded(true);
    }
  }, [routeId, agencies, isLoading, loaded]);

  const patch = (p: Partial<AgencyFormState>) => setForm((f) => ({ ...f, ...p }));

  const stepValid: Record<WizardStepId, boolean> = {
    general: isStepGeneralValid(form),
    connection: isStepConnectionValid(form),
    test: true,
    routing: true,
    review: true,
  };

  const persistDraft = async (): Promise<string> => {
    const payload = {
      ...buildSavePayload(form, parseExpectedPayload(form.expectedPayload).value),
      status: agencyId ? form.status : ("draft" as const),
    };
    if (agencyId) {
      await updateMutation.mutateAsync({ ...payload, id: agencyId });
      return agencyId;
    }
    const created = await createMutation.mutateAsync(payload);
    setAgencyId(created.id);
    return created.id;
  };

  const goNext = async () => {
    const idx = stepIndex(step);
    // Leaving the connection step persists the draft so the test step has an id.
    if (step === "connection") {
      try {
        await persistDraft();
      } catch (err: unknown) {
        toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
        return;
      }
    }
    setStep(WIZARD_STEPS[idx + 1].id);
  };

  const goBack = () => {
    const idx = stepIndex(step);
    if (idx === 0) navigate("/agencies");
    else setStep(WIZARD_STEPS[idx - 1].id);
  };

  const saveDraftAndExit = async () => {
    try {
      const id = await persistDraft();
      toast.success("บันทึก Draft สำเร็จ");
      navigate(`/agencies/${id}`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
    }
  };

  const currentIdx = stepIndex(step);

  return (
    <div className="p-4 md:p-6">
      <Button variant="ghost" size="sm" onClick={() => navigate("/agencies")} className="mb-4">
        <ArrowLeft className="h-4 w-4 mr-1" /> กลับ
      </Button>
      <div className="flex gap-8">
        <nav className="w-48 shrink-0 space-y-1">
          {WIZARD_STEPS.map((s, i) => (
            <div
              key={s.id}
              className={`flex items-center gap-2 text-sm rounded-md px-3 py-2 ${
                s.id === step
                  ? "bg-accent font-medium text-foreground"
                  : i < currentIdx
                    ? "text-foreground"
                    : "text-muted-foreground"
              }`}
            >
              {i < currentIdx ? (
                <Check className="h-3.5 w-3.5 text-green-600" />
              ) : (
                <span className="w-3.5 text-center text-xs">{i + 1}</span>
              )}
              {s.label}
            </div>
          ))}
        </nav>

        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-semibold mb-4">{WIZARD_STEPS[currentIdx].label}</h2>

          {step === "general" && <StepGeneral form={form} patch={patch} />}
          {step === "connection" && (
            <div className="space-y-4 max-w-lg">
              <div className="space-y-1.5">
                <Label htmlFor="wiz-endpoint">Endpoint URL</Label>
                <Input
                  id="wiz-endpoint"
                  value={form.endpointUrl}
                  onChange={(e) => patch({ endpointUrl: e.target.value })}
                />
              </div>
            </div>
          )}
          {step === "test" && <p className="text-sm text-muted-foreground">(test step — Task 10)</p>}
          {step === "routing" && <p className="text-sm text-muted-foreground">(routing step — Task 11)</p>}
          {step === "review" && <p className="text-sm text-muted-foreground">(review step — Task 11)</p>}

          <div className="flex items-center justify-between mt-8 max-w-lg">
            <Button variant="ghost" onClick={goBack}>
              ย้อนกลับ
            </Button>
            <div className="flex gap-2">
              {currentIdx >= stepIndex("connection") && step !== "review" && (
                <Button variant="outline" onClick={saveDraftAndExit} disabled={!stepValid.general}>
                  บันทึก Draft
                </Button>
              )}
              {step !== "review" && (
                <Button onClick={goNext} disabled={!stepValid[step]}>
                  ถัดไป
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Wire routes**

In `frontend/src/App.tsx` add the import and two routes **before** the `/agencies/:id` route:

```tsx
import AgencyWizardPage from "@/features/agencies/wizard/AgencyWizardPage";
```

```tsx
                <Route path="/agencies/new" element={<AgencyWizardPage />} />
                <Route path="/agencies/:id/setup" element={<AgencyWizardPage />} />
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/wizard/AgencyWizardPage.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 7: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/wizard frontend/src/App.tsx
rtk git commit -m "feat(agencies): add full-page setup wizard scaffold with StepGeneral"
```

---

### Task 9: StepConnection (per-type fields, headers editor, MCP discovery)

**Files:**
- Create: `frontend/src/features/agencies/wizard/StepConnection.tsx`
- Create: `frontend/src/features/agencies/wizard/HeadersEditor.tsx`
- Modify: `frontend/src/features/agencies/wizard/AgencyWizardPage.tsx` (swap placeholder)
- Test: `frontend/src/features/agencies/wizard/StepConnection.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/wizard/StepConnection.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { server } from "@/mocks/server";

import { DEFAULT_FORM_STATE, type AgencyFormState } from "../agencyForm";
import { StepConnection } from "./StepConnection";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function wrap(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("StepConnection", () => {
  it("shows API fields for API type", () => {
    const form: AgencyFormState = { ...DEFAULT_FORM_STATE, connectionType: "API" };
    render(wrap(<StepConnection form={form} patch={vi.fn()} />));
    expect(screen.getByLabelText("Endpoint URL")).toBeInTheDocument();
    expect(screen.getByLabelText(/Expected payload/)).toBeInTheDocument();
    expect(screen.getByText(/Headers/)).toBeInTheDocument();
  });

  it("shows only endpoint for A2A", () => {
    const form: AgencyFormState = { ...DEFAULT_FORM_STATE, connectionType: "A2A" };
    render(wrap(<StepConnection form={form} patch={vi.fn()} />));
    expect(screen.getByLabelText("Endpoint URL")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Expected payload/)).not.toBeInTheDocument();
  });

  it("discovers MCP tools and selects one", async () => {
    const patch = vi.fn();
    const form: AgencyFormState = {
      ...DEFAULT_FORM_STATE,
      connectionType: "MCP",
      endpointUrl: "https://mcp.example/sse",
    };
    render(wrap(<StepConnection form={form} patch={patch} />));
    await userEvent.click(screen.getByRole("button", { name: /Discover tools/ }));
    await waitFor(() => expect(screen.getByText("chat_with_fda")).toBeInTheDocument());
    await userEvent.click(screen.getByText("chat_with_fda"));
    expect(patch).toHaveBeenCalledWith({ mcpToolName: "chat_with_fda" });
  });

  it("switches connection type via patch", async () => {
    const patch = vi.fn();
    render(wrap(<StepConnection form={DEFAULT_FORM_STATE} patch={patch} />));
    await userEvent.click(screen.getByRole("button", { name: "MCP" }));
    expect(patch).toHaveBeenCalledWith({ connectionType: "MCP" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/wizard/StepConnection.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement HeadersEditor**

Create `frontend/src/features/agencies/wizard/HeadersEditor.tsx` (replacement for the dialog-era `AgencyHeadersEditor`):

```tsx
import { Plus, X } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import type { ApiHeader } from "@/shared/types/agency";

interface Props {
  headers: ApiHeader[];
  onChange: (headers: ApiHeader[]) => void;
}

export function HeadersEditor({ headers, onChange }: Props) {
  const update = (i: number, field: keyof ApiHeader, value: string) => {
    onChange(headers.map((h, idx) => (idx === i ? { ...h, [field]: value } : h)));
  };

  return (
    <div className="space-y-2">
      {headers.map((h, i) => (
        <div key={i} className="flex gap-2">
          <Input placeholder="Header name" value={h.name} onChange={(e) => update(i, "name", e.target.value)} />
          <Input placeholder="Value" value={h.value} onChange={(e) => update(i, "value", e.target.value)} />
          <Button variant="ghost" size="icon" onClick={() => onChange(headers.filter((_, idx) => idx !== i))}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={() => onChange([...headers, { name: "", value: "" }])}>
        <Plus className="h-3.5 w-3.5 mr-1" /> เพิ่ม header
      </Button>
    </div>
  );
}
```

- [ ] **Step 4: Implement StepConnection**

Create `frontend/src/features/agencies/wizard/StepConnection.tsx`:

```tsx
import { Search } from "lucide-react";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";
import type { Agency } from "@/shared/types/agency";

import { parseExpectedPayload, PROTOCOL_INFO, type AgencyFormState } from "../agencyForm";
import { useDiscoverMcpTools } from "../useAgencies";
import { HeadersEditor } from "./HeadersEditor";

const CONNECTION_TYPES: Agency["connectionType"][] = ["API", "MCP", "A2A"];

interface Props {
  form: AgencyFormState;
  patch: (p: Partial<AgencyFormState>) => void;
}

export function StepConnection({ form, patch }: Props) {
  const discover = useDiscoverMcpTools();
  const payloadError = parseExpectedPayload(form.expectedPayload).error;

  return (
    <div className="space-y-5 max-w-lg">
      <div className="space-y-1.5">
        <Label>ประเภทการเชื่อมต่อ</Label>
        <div className="flex gap-2">
          {CONNECTION_TYPES.map((t) => (
            <Button
              key={t}
              type="button"
              variant={form.connectionType === t ? "default" : "outline"}
              size="sm"
              onClick={() => patch({ connectionType: t })}
            >
              {t}
            </Button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{PROTOCOL_INFO[form.connectionType]}</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="wiz-endpoint">Endpoint URL</Label>
        <Input
          id="wiz-endpoint"
          placeholder="https://…"
          value={form.endpointUrl}
          onChange={(e) => patch({ endpointUrl: e.target.value })}
        />
      </div>

      {form.connectionType === "API" && (
        <>
          <div className="space-y-1.5">
            <Label>Headers</Label>
            <HeadersEditor headers={form.apiHeaders} onChange={(apiHeaders) => patch({ apiHeaders })} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wiz-payload">Expected payload (JSON template)</Label>
            <Textarea
              id="wiz-payload"
              rows={5}
              placeholder='{"query": "__query__", "session_id": "__session_id__"}'
              value={form.expectedPayload}
              onChange={(e) => patch({ expectedPayload: e.target.value })}
              className="font-mono text-xs"
            />
            {payloadError && <p className="text-xs text-destructive">JSON ไม่ถูกต้อง</p>}
          </div>
        </>
      )}

      {form.connectionType === "MCP" && (
        <div className="space-y-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!form.endpointUrl.trim() || discover.isPending}
            onClick={() => discover.mutate({ endpointUrl: form.endpointUrl })}
          >
            <Search className="h-3.5 w-3.5 mr-1" />
            {discover.isPending ? "กำลังค้นหา…" : "Discover tools"}
          </Button>
          {discover.isError && (
            <p className="text-xs text-destructive">
              ค้นหา tools ไม่สำเร็จ: {discover.error.message} — ลองใหม่ได้ หรือบันทึก Draft ไว้ก่อน
            </p>
          )}
          {discover.data && (
            <div className="space-y-1">
              {discover.data.map((tool) => (
                <button
                  key={tool.name}
                  type="button"
                  onClick={() => patch({ mcpToolName: tool.name })}
                  className={`w-full text-left rounded-md border px-3 py-2 text-sm ${
                    form.mcpToolName === tool.name ? "border-primary bg-accent" : "border-border"
                  }`}
                >
                  <span className="font-mono">{tool.name}</span>
                  <span className="block text-xs text-muted-foreground">{tool.description}</span>
                </button>
              ))}
            </div>
          )}
          {form.mcpToolName && !discover.data && (
            <p className="text-xs text-muted-foreground">
              Tool ที่เลือกไว้: <span className="font-mono">{form.mcpToolName}</span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Swap the placeholder in AgencyWizardPage**

In `AgencyWizardPage.tsx`, replace the inline connection-step block from Task 8 with:

```tsx
          {step === "connection" && <StepConnection form={form} patch={patch} />}
```

Add the import `import { StepConnection } from "./StepConnection";` and remove the now-unused `Input`/`Label` imports from the wizard page.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/wizard/`
Expected: PASS (StepConnection 4 tests + scaffold 3 tests still green).

- [ ] **Step 7: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/wizard
rtk git commit -m "feat(agencies): add wizard connection step with MCP tool discovery"
```

---

### Task 10: StepTest

**Files:**
- Create: `frontend/src/features/agencies/wizard/StepTest.tsx`
- Modify: `frontend/src/features/agencies/wizard/AgencyWizardPage.tsx` (swap placeholder)
- Test: `frontend/src/features/agencies/wizard/StepTest.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/wizard/StepTest.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";

import { resetMockData } from "@/mocks/fixtures";
import { server } from "@/mocks/server";

import { StepTest } from "./StepTest";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  resetMockData();
});
afterAll(() => server.close());

const ACTIVE_ID = "11111111-1111-1111-1111-111111111111";

function wrap(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("StepTest", () => {
  it("runs the connection test and shows the result", async () => {
    render(wrap(<StepTest agencyId={ACTIVE_ID} />));
    await userEvent.click(screen.getByRole("button", { name: /ทดสอบการเชื่อมต่อ/ }));
    await waitFor(() => expect(screen.getByText(/Handshake/)).toBeInTheDocument());
  });

  it("shows a non-blocking failure message on error", async () => {
    server.use(
      http.get("*/api/v1/agencies/:id/test", () =>
        HttpResponse.json({ detail: "boom" }, { status: 502 }),
      ),
    );
    render(wrap(<StepTest agencyId={ACTIVE_ID} />));
    await userEvent.click(screen.getByRole("button", { name: /ทดสอบการเชื่อมต่อ/ }));
    await waitFor(() => expect(screen.getByText(/ไม่สำเร็จ/)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/wizard/StepTest.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/features/agencies/wizard/StepTest.tsx`:

```tsx
import { Wifi } from "lucide-react";

import { Button } from "@/shared/components/ui/button";

import { ConnectionTestResult } from "../ConnectionTestResult";
import { useTestConnection } from "../useAgencies";

interface Props {
  agencyId: string;
}

export function StepTest({ agencyId }: Props) {
  const testMutation = useTestConnection();

  return (
    <div className="space-y-4 max-w-lg">
      <p className="text-sm text-muted-foreground">
        ทดสอบการเชื่อมต่อกับ endpoint ที่ตั้งค่าไว้ — หากไม่สำเร็จยังสามารถบันทึกเป็น Draft แล้วกลับมาแก้ไขภายหลังได้
      </p>
      <Button onClick={() => testMutation.mutate({ agencyId })} disabled={testMutation.isPending}>
        <Wifi className="h-4 w-4 mr-1.5" />
        {testMutation.isPending ? "กำลังทดสอบ…" : "ทดสอบการเชื่อมต่อ"}
      </Button>
      {(testMutation.isPending || testMutation.data || testMutation.isError) && (
        <ConnectionTestResult
          result={
            testMutation.data ??
            (testMutation.isError
              ? { success: false, error: `ทดสอบไม่สำเร็จ: ${testMutation.error?.message ?? "Request failed"}` }
              : null)
          }
          loading={testMutation.isPending}
        />
      )}
    </div>
  );
}
```

(Check `ConnectionTestResult`'s `TestResult` interface when implementing — pass only fields it declares; the failure object above must satisfy it. If `error` alone is not enough to render the "ไม่สำเร็จ" text, render the failure message in a `<p className="text-destructive">` next to the component instead.)

- [ ] **Step 4: Swap the placeholder in AgencyWizardPage**

Replace the test-step placeholder with:

```tsx
          {step === "test" && agencyId && <StepTest agencyId={agencyId} />}
```

Add `import { StepTest } from "./StepTest";`. (`agencyId` is always set here because leaving the connection step persists the draft.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/wizard/`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/wizard
rtk git commit -m "feat(agencies): add wizard connection-test step"
```

---

### Task 11: StepRouting, StepReview, DataScopeEditor — wizard complete

**Files:**
- Create: `frontend/src/features/agencies/DataScopeEditor.tsx` (shared with detail RoutingTab later)
- Create: `frontend/src/features/agencies/wizard/StepRouting.tsx`
- Create: `frontend/src/features/agencies/wizard/StepReview.tsx`
- Modify: `frontend/src/features/agencies/wizard/AgencyWizardPage.tsx`
- Test: `frontend/src/features/agencies/wizard/wizardFlow.test.tsx`

- [ ] **Step 1: Write the failing end-to-end wizard test**

Create `frontend/src/features/agencies/wizard/wizardFlow.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { mockAgencies, resetMockData } from "@/mocks/fixtures";
import { server } from "@/mocks/server";

import AgencyWizardPage from "./AgencyWizardPage";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  resetMockData();
});
afterAll(() => server.close());

function renderWizard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/agencies/new"]}>
        <Routes>
          <Route path="/agencies/new" element={<AgencyWizardPage />} />
          <Route path="/agencies/:id" element={<div>detail-page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("wizard full flow (API agency)", () => {
  it("creates an active agency through all five steps", async () => {
    const user = userEvent.setup();
    renderWizard();

    // Step 1 — general
    await user.type(screen.getByLabelText("ชื่อหน่วยงาน"), "กรมศุลกากร");
    await user.type(screen.getByLabelText("ชื่อย่อ"), "ศก.");
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));

    // Step 2 — connection (API default)
    await user.type(screen.getByLabelText("Endpoint URL"), "https://customs.example/api/chat");
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));

    // Draft was persisted on leaving step 2
    await waitFor(() => expect(mockAgencies.some((a) => a.name === "กรมศุลกากร")).toBe(true));
    const created = mockAgencies.find((a) => a.name === "กรมศุลกากร")!;
    expect(created.status).toBe("draft");

    // Step 3 — test (optional, skip)
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));

    // Step 4 — routing
    await user.type(screen.getByLabelText(/Router hint/), "คำถามภาษีนำเข้า");
    await user.type(screen.getByLabelText(/Priority/), "2");
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));

    // Step 5 — review shows entered data, then activate
    expect(screen.getByText("กรมศุลกากร")).toBeInTheDocument();
    expect(screen.getByText("https://customs.example/api/chat")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /เปิดใช้งาน/ }));

    await waitFor(() => expect(screen.getByText("detail-page")).toBeInTheDocument());
    const final = mockAgencies.find((a) => a.name === "กรมศุลกากร")!;
    expect(final.status).toBe("active");
    expect(final.router_hint).toBe("คำถามภาษีนำเข้า");
    expect(final.priority).toBe(2);
  });

  it("saves as draft from the review step", async () => {
    const user = userEvent.setup();
    renderWizard();

    await user.type(screen.getByLabelText("ชื่อหน่วยงาน"), "กรมป่าไม้");
    await user.type(screen.getByLabelText("ชื่อย่อ"), "ปม.");
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));
    await user.type(screen.getByLabelText("Endpoint URL"), "https://forest.example/api");
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));
    await user.click(screen.getByRole("button", { name: /บันทึกเป็น Draft/ }));

    await waitFor(() => expect(screen.getByText("detail-page")).toBeInTheDocument());
    expect(mockAgencies.find((a) => a.name === "กรมป่าไม้")!.status).toBe("draft");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/wizard/wizardFlow.test.tsx`
Expected: FAIL — routing/review steps are placeholders.

- [ ] **Step 3: Implement DataScopeEditor**

Create `frontend/src/features/agencies/DataScopeEditor.tsx`:

```tsx
import { Plus, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";

interface Props {
  scope: string[];
  onChange: (scope: string[]) => void;
}

export function DataScopeEditor({ scope, onChange }: Props) {
  const [input, setInput] = useState("");

  const add = () => {
    const value = input.trim();
    if (value && !scope.includes(value)) onChange([...scope, value]);
    setInput("");
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {scope.map((s) => (
          <span
            key={s}
            className="inline-flex items-center gap-1 text-xs bg-accent text-accent-foreground px-2 py-0.5 rounded-full"
          >
            {s}
            <button type="button" onClick={() => onChange(scope.filter((x) => x !== s))} aria-label={`ลบ ${s}`}>
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <Input
          placeholder="เพิ่มขอบเขตข้อมูล เช่น ภาษี"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <Button type="button" variant="outline" size="icon" onClick={add} aria-label="เพิ่มขอบเขต">
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement StepRouting**

Create `frontend/src/features/agencies/wizard/StepRouting.tsx`:

```tsx
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";

import { DataScopeEditor } from "../DataScopeEditor";
import type { AgencyFormState } from "../agencyForm";

interface Props {
  form: AgencyFormState;
  patch: (p: Partial<AgencyFormState>) => void;
}

export function StepRouting({ form, patch }: Props) {
  return (
    <div className="space-y-5 max-w-lg">
      <div className="space-y-1.5">
        <Label>ขอบเขตข้อมูล (data scope)</Label>
        <DataScopeEditor scope={form.dataScope} onChange={(dataScope) => patch({ dataScope })} />
        <p className="text-xs text-muted-foreground">คีย์เวิร์ดที่ router ใช้พิจารณาเลือกหน่วยงานนี้</p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="wiz-hint">Router hint</Label>
        <Textarea
          id="wiz-hint"
          rows={3}
          placeholder="อธิบายว่าหน่วยงานนี้ตอบคำถามแบบใด เพื่อช่วย LLM router ตัดสินใจ"
          value={form.routerHint}
          onChange={(e) => patch({ routerHint: e.target.value })}
        />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="wiz-priority">Priority</Label>
          <Input
            id="wiz-priority"
            type="number"
            min={1}
            placeholder="เช่น 1"
            value={form.priority}
            onChange={(e) => patch({ priority: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wiz-timeout">Timeout (วินาที)</Label>
          <Input
            id="wiz-timeout"
            type="number"
            min={1}
            placeholder="ค่าเริ่มต้นระบบ"
            value={form.dispatchTimeoutS}
            onChange={(e) => patch({ dispatchTimeoutS: e.target.value })}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wiz-rpm">Rate limit (rpm)</Label>
          <Input
            id="wiz-rpm"
            type="number"
            min={1}
            placeholder="ไม่จำกัด"
            value={form.rateLimitRpm}
            onChange={(e) => patch({ rateLimitRpm: e.target.value })}
          />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Implement StepReview**

Create `frontend/src/features/agencies/wizard/StepReview.tsx`:

```tsx
import { Badge } from "@/shared/components/ui/badge";

import type { AgencyFormState } from "../agencyForm";

interface Props {
  form: AgencyFormState;
}

function Row({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div className="flex justify-between gap-4 py-1.5 border-b border-border last:border-0">
      <span className="text-xs text-muted-foreground shrink-0">{label}</span>
      <span className="text-xs text-right break-all">{value}</span>
    </div>
  );
}

export function StepReview({ form }: Props) {
  return (
    <div className="max-w-lg space-y-4">
      <div className="flex items-center gap-3">
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
          style={{ backgroundColor: `${form.color}15` }}
        >
          {form.logo}
        </div>
        <div>
          <p className="font-medium">{form.name}</p>
          <p className="text-xs text-muted-foreground">{form.shortName}</p>
        </div>
        <Badge className="ml-auto">{form.connectionType}</Badge>
      </div>
      <div className="rounded-lg border border-border p-4">
        <Row label="Endpoint" value={form.endpointUrl} />
        <Row label="คำอธิบาย" value={form.description} />
        <Row label="MCP tool" value={form.mcpToolName} />
        <Row label="ขอบเขตข้อมูล" value={form.dataScope.join(", ")} />
        <Row label="Router hint" value={form.routerHint} />
        <Row label="Priority" value={form.priority} />
        <Row label="Timeout (s)" value={form.dispatchTimeoutS} />
        <Row label="Rate limit (rpm)" value={form.rateLimitRpm} />
      </div>
      <p className="text-xs text-muted-foreground">
        "เปิดใช้งาน" จะตั้งสถานะเป็น Active และเข้าร่วมการ routing ทันที — หรือบันทึกเป็น Draft เพื่อกลับมาแก้ไขภายหลัง
      </p>
    </div>
  );
}
```

- [ ] **Step 6: Finish AgencyWizardPage**

In `AgencyWizardPage.tsx`:

1. Replace the routing/review placeholders:

```tsx
          {step === "routing" && <StepRouting form={form} patch={patch} />}
          {step === "review" && <StepReview form={form} />}
```

2. Add imports for `StepRouting`, `StepReview`, `canActivate` (from `../agencyForm`), and `useUpdateAgencyStatus` (from `../useAgencies`).

3. Add the finish actions inside the component:

```tsx
  const statusMutation = useUpdateAgencyStatus();

  const finish = async (activate: boolean) => {
    try {
      const id = await persistDraft();
      if (activate) await statusMutation.mutateAsync({ id, status: "active" });
      toast.success(activate ? "เปิดใช้งานหน่วยงานสำเร็จ" : "บันทึกเป็น Draft สำเร็จ");
      navigate(`/agencies/${id}`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
    }
  };
```

Note: `finish(true)` on a resumed non-draft agency (status already `active`) must NOT call the status transition — guard with `if (activate && form.status !== "active")`.

4. In the footer buttons block, add the review-step actions next to the existing buttons:

```tsx
              {step === "review" && (
                <>
                  <Button variant="outline" onClick={() => finish(false)}>
                    บันทึกเป็น Draft
                  </Button>
                  <Button onClick={() => finish(true)} disabled={!canActivate(form)}>
                    เปิดใช้งาน
                  </Button>
                </>
              )}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/wizard/`
Expected: PASS (all wizard tests, including the two flow tests).

- [ ] **Step 8: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/wizard frontend/src/features/agencies/DataScopeEditor.tsx
rtk git commit -m "feat(agencies): complete wizard with routing, review, and activation"
```

---

### Task 12: Detail page scaffold — header, lifecycle dropdown, Overview + Logs tabs

**Files:**
- Create: `frontend/src/features/agencies/detail/AgencyDetailPage.tsx`
- Create: `frontend/src/features/agencies/detail/OverviewTab.tsx`
- Create: `frontend/src/features/agencies/detail/LogsTab.tsx`
- Modify: `frontend/src/App.tsx` (point `/agencies/:id` at the new page)
- Test: `frontend/src/features/agencies/detail/AgencyDetailPage.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/detail/AgencyDetailPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { mockAgencies, resetMockData } from "@/mocks/fixtures";
import { server } from "@/mocks/server";

import AgencyDetailPage from "./AgencyDetailPage";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  resetMockData();
});
afterAll(() => server.close());

const ACTIVE_ID = "11111111-1111-1111-1111-111111111111";
const DRAFT_ID = "33333333-3333-3333-3333-333333333333";

function renderDetail(id: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/agencies/${id}`]}>
        <Routes>
          <Route path="/agencies/:id" element={<AgencyDetailPage />} />
          <Route path="/agencies/:id/setup" element={<div>wizard</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AgencyDetailPage", () => {
  it("renders header with status badge and the five tabs", async () => {
    renderDetail(ACTIVE_ID);
    await waitFor(() => expect(screen.getByText("กรมสรรพากร")).toBeInTheDocument());
    expect(screen.getByText("Active")).toBeInTheDocument();
    for (const tab of ["ภาพรวม", "Health", "การเชื่อมต่อ", "Routing", "Logs"]) {
      expect(screen.getByRole("tab", { name: new RegExp(tab) })).toBeInTheDocument();
    }
  });

  it("offers only legal transitions in the status dropdown and applies one", async () => {
    const user = userEvent.setup();
    renderDetail(ACTIVE_ID);
    await waitFor(() => expect(screen.getByText("กรมสรรพากร")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /สถานะ/ }));
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByText("ปิดปรับปรุง")).toBeInTheDocument();
    expect(within(menu).getByText("ปิดการใช้งาน")).toBeInTheDocument();
    expect(within(menu).queryByText("เปิดใช้งาน")).not.toBeInTheDocument();
    await user.click(within(menu).getByText("ปิดปรับปรุง"));
    await waitFor(() =>
      expect(mockAgencies.find((a) => a.id === ACTIVE_ID)!.status).toBe("maintenance"),
    );
  });

  it("shows a continue-setup banner for drafts", async () => {
    renderDetail(DRAFT_ID);
    await waitFor(() => expect(screen.getByText("กรมที่ดิน")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /ตั้งค่าต่อ/ })).toHaveAttribute(
      "href",
      `/agencies/${DRAFT_ID}/setup`,
    );
  });

  it("shows overview stat cards", async () => {
    renderDetail(ACTIVE_ID);
    await waitFor(() => expect(screen.getByText("กรมสรรพากร")).toBeInTheDocument());
    expect(screen.getByText(/99.2%/)).toBeInTheDocument();
    expect(screen.getByText(/320/)).toBeInTheDocument();
    expect(screen.getByText("1,204")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/detail/AgencyDetailPage.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement OverviewTab**

Create `frontend/src/features/agencies/detail/OverviewTab.tsx`:

```tsx
import { Line, LineChart, ResponsiveContainer } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import type { Agency } from "@/shared/types/agency";

import { HEALTH_LABEL } from "../lifecycle";
import { useHealthHistory } from "../useAgencies";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-xs font-normal text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  );
}

export function OverviewTab({ agency }: { agency: Agency }) {
  const { data: history } = useHealthHistory(agency.id, "24h");
  const h = agency.health;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Stat label="Uptime 24 ชม." value={h.uptime24h != null ? `${h.uptime24h}%` : "—"} />
        <Stat label="Latency เฉลี่ย" value={h.avgLatencyMs24h != null ? `${h.avgLatencyMs24h} ms` : "—"} />
        <Stat label="จำนวนครั้งที่เรียกใช้" value={agency.totalCalls.toLocaleString()} />
        <Stat label="คะแนน" value={`👍 ${agency.ratingUp} · 👎 ${agency.ratingDown}`} />
      </div>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">
            สุขภาพ 24 ชั่วโมง — {HEALTH_LABEL[h.state]}
          </CardTitle>
        </CardHeader>
        <CardContent className="h-24">
          {history && history.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <Line type="monotone" dataKey="avgLatencyMs" stroke="hsl(213 70% 45%)" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-xs text-muted-foreground">ยังไม่มีข้อมูล</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Implement LogsTab**

Create `frontend/src/features/agencies/detail/LogsTab.tsx` (thin wrapper over the kept component):

```tsx
import { useConnectionLogs } from "@/features/connection-logs/useConnectionLogs";

import { AgencyConnectionLogsTab } from "../AgencyConnectionLogsTab";

export function LogsTab({ agencyId }: { agencyId: string }) {
  const { data: logs, isLoading } = useConnectionLogs({ agencyId });
  return <AgencyConnectionLogsTab logs={logs} logsLoading={isLoading} />;
}
```

(Match `AgencyConnectionLogsTab`'s actual prop names when implementing — read the file first.)

- [ ] **Step 5: Implement the detail page**

Create `frontend/src/features/agencies/detail/AgencyDetailPage.tsx`:

```tsx
import { ArrowLeft, ArrowRight, ChevronDown } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs";
import type { AgencyLifecycleStatus } from "@/shared/types/agency";

import {
  HEALTH_DOT_CLASS,
  legalTransitions,
  STATUS_BADGE_CLASS,
  STATUS_LABEL,
  TRANSITION_LABEL,
} from "../lifecycle";
import { useAgencies, useUpdateAgencyStatus } from "../useAgencies";
import { LogsTab } from "./LogsTab";
import { OverviewTab } from "./OverviewTab";

export default function AgencyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: agencies = [], isLoading } = useAgencies();
  const statusMutation = useUpdateAgencyStatus();

  const agency = agencies.find((a) => a.id === id);

  if (isLoading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!agency) {
    return (
      <div className="p-4 md:p-6 text-center space-y-4">
        <p className="text-muted-foreground">ไม่พบหน่วยงาน</p>
        <Button variant="outline" onClick={() => navigate("/agencies")}>
          <ArrowLeft className="h-4 w-4 mr-2" /> กลับ
        </Button>
      </div>
    );
  }

  const changeStatus = async (status: AgencyLifecycleStatus) => {
    try {
      await statusMutation.mutateAsync({ id: agency.id, status });
      toast.success(`เปลี่ยนสถานะเป็น ${STATUS_LABEL[status]} สำเร็จ`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
    }
  };

  const showHealthDot = agency.status === "active" || agency.status === "maintenance";

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/agencies")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
            style={{ backgroundColor: `${agency.color}15` }}
          >
            {agency.logo}
          </div>
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2">
              {agency.name}
              {showHealthDot && (
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${HEALTH_DOT_CLASS[agency.health.state]}`} />
              )}
            </h2>
            <div className="flex items-center gap-2 mt-1">
              <Badge className={`text-[10px] ${STATUS_BADGE_CLASS[agency.status]}`}>
                {STATUS_LABEL[agency.status]}
              </Badge>
              <Badge variant="outline" className="text-[10px]">{agency.connectionType}</Badge>
            </div>
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              สถานะ <ChevronDown className="h-3.5 w-3.5 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {legalTransitions(agency.status).map((to) => (
              <DropdownMenuItem key={to} onClick={() => changeStatus(to)}>
                {TRANSITION_LABEL[to]}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {agency.status === "draft" && (
        <div className="rounded-lg border border-dashed border-border p-4 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">หน่วยงานนี้ยังตั้งค่าไม่เสร็จ</p>
          <Link
            to={`/agencies/${agency.id}/setup`}
            className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            ตั้งค่าต่อ <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">ภาพรวม</TabsTrigger>
          <TabsTrigger value="health">Health</TabsTrigger>
          <TabsTrigger value="connection">การเชื่อมต่อ</TabsTrigger>
          <TabsTrigger value="routing">Routing</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">
          <OverviewTab agency={agency} />
        </TabsContent>
        <TabsContent value="health">
          <p className="text-sm text-muted-foreground">(Health tab — Task 13)</p>
        </TabsContent>
        <TabsContent value="connection">
          <p className="text-sm text-muted-foreground">(Connection tab — Task 14)</p>
        </TabsContent>
        <TabsContent value="routing">
          <p className="text-sm text-muted-foreground">(Routing tab — Task 14)</p>
        </TabsContent>
        <TabsContent value="logs">
          <LogsTab agencyId={agency.id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 6: Point the route at the new page**

In `frontend/src/App.tsx`, change the detail import:

```tsx
import AgencyDetailPage from "@/features/agencies/detail/AgencyDetailPage";
```

(The old `frontend/src/features/agencies/AgencyDetailPage.tsx` is now unreferenced; it is deleted in Task 15.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/detail/`
Expected: PASS (4 tests).

- [ ] **Step 8: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/detail frontend/src/App.tsx
rtk git commit -m "feat(agencies): add tabbed detail page with lifecycle dropdown and overview"
```

---

### Task 13: HealthTab — charts, window switching, error state

**Files:**
- Create: `frontend/src/features/agencies/detail/HealthTab.tsx`
- Modify: `frontend/src/features/agencies/detail/AgencyDetailPage.tsx` (swap placeholder)
- Test: `frontend/src/features/agencies/detail/HealthTab.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/detail/HealthTab.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";

import { resetMockData } from "@/mocks/fixtures";
import { server } from "@/mocks/server";

import { HealthTab } from "./HealthTab";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  resetMockData();
});
afterAll(() => server.close());

const ACTIVE_ID = "11111111-1111-1111-1111-111111111111";

function wrap(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("HealthTab", () => {
  it("renders uptime and latency charts for the default 24h window", async () => {
    render(wrap(<HealthTab agencyId={ACTIVE_ID} />));
    await waitFor(() => expect(screen.getByText(/Uptime/)).toBeInTheDocument());
    expect(screen.getByText(/Latency/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "24h" })).toBeInTheDocument();
  });

  it("switches window", async () => {
    render(wrap(<HealthTab agencyId={ACTIVE_ID} />));
    await waitFor(() => expect(screen.getByText(/Uptime/)).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "7d" }));
    // 7d stays selected (variant switch) — assert via aria-pressed
    expect(screen.getByRole("button", { name: "7d" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows an error state with retry when history fails", async () => {
    server.use(
      http.get("*/api/v1/agencies/:id/health/history", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    render(wrap(<HealthTab agencyId={ACTIVE_ID} />));
    await waitFor(() => expect(screen.getByText(/โหลดข้อมูลไม่สำเร็จ/)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /ลองใหม่/ })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/detail/HealthTab.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/features/agencies/detail/HealthTab.tsx`:

```tsx
import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/shared/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import type { HealthWindow } from "@/shared/types/agency";

import { useHealthHistory } from "../useAgencies";

const WINDOWS: HealthWindow[] = ["24h", "7d", "30d"];

export function HealthTab({ agencyId }: { agencyId: string }) {
  // "win" not "window" — avoid shadowing the global.
  const [win, setWin] = useState<HealthWindow>("24h");
  const { data, isLoading, isError, refetch } = useHealthHistory(agencyId, win);

  const chartData = (data ?? []).map((b) => ({
    ...b,
    time: new Date(b.bucketStart).toLocaleString("th-TH", {
      day: win === "24h" ? undefined : "numeric",
      month: win === "24h" ? undefined : "short",
      hour: win === "30d" ? undefined : "2-digit",
      minute: win === "30d" ? undefined : "2-digit",
    }),
  }));

  if (isError) {
    return (
      <div className="rounded-lg border border-border p-8 text-center space-y-3">
        <p className="text-sm text-muted-foreground">โหลดข้อมูลไม่สำเร็จ</p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          ลองใหม่
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {WINDOWS.map((w) => (
          <Button
            key={w}
            size="sm"
            variant={win === w ? "default" : "outline"}
            aria-pressed={win === w}
            onClick={() => setWin(w)}
          >
            {w}
          </Button>
        ))}
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Uptime (%)</CardTitle>
        </CardHeader>
        <CardContent className="h-48">
          {isLoading ? (
            <p className="text-xs text-muted-foreground">กำลังโหลด…</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} minTickGap={32} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} width={32} />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="uptimePct"
                  name="uptime %"
                  stroke="hsl(152 55% 42%)"
                  fill="hsl(152 55% 42% / 0.15)"
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Latency (ms)</CardTitle>
        </CardHeader>
        <CardContent className="h-48">
          {isLoading ? (
            <p className="text-xs text-muted-foreground">กำลังโหลด…</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} minTickGap={32} />
                <YAxis tick={{ fontSize: 10 }} width={40} />
                <Tooltip />
                <Line type="monotone" dataKey="avgLatencyMs" name="latency ms" stroke="hsl(213 70% 45%)" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Swap the placeholder**

In `detail/AgencyDetailPage.tsx`:

```tsx
        <TabsContent value="health">
          <HealthTab agencyId={agency.id} />
        </TabsContent>
```

Add `import { HealthTab } from "./HealthTab";`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/detail/`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/detail
rtk git commit -m "feat(agencies): add health tab with uptime/latency charts"
```

---

### Task 14: ConnectionTab + RoutingTab (inline editing)

**Files:**
- Create: `frontend/src/features/agencies/detail/ConnectionTab.tsx`
- Create: `frontend/src/features/agencies/detail/RoutingTab.tsx`
- Modify: `frontend/src/features/agencies/detail/AgencyDetailPage.tsx` (swap placeholders)
- Test: `frontend/src/features/agencies/detail/editTabs.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/agencies/detail/editTabs.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { mockAgencies, resetMockData } from "@/mocks/fixtures";
import { server } from "@/mocks/server";
import { mapRowToAgency } from "@/shared/types/agency";

import { ConnectionTab } from "./ConnectionTab";
import { RoutingTab } from "./RoutingTab";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  resetMockData();
});
afterAll(() => server.close());

const ACTIVE_ID = "11111111-1111-1111-1111-111111111111";

function wrap(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function activeAgency() {
  return mapRowToAgency(mockAgencies.find((a) => a.id === ACTIVE_ID)!);
}

describe("ConnectionTab", () => {
  it("saves an edited endpoint", async () => {
    const user = userEvent.setup();
    render(wrap(<ConnectionTab agency={activeAgency()} />));
    const input = screen.getByLabelText("Endpoint URL");
    await user.clear(input);
    await user.type(input, "https://rd-new.example/api/chat");
    await user.click(screen.getByRole("button", { name: /บันทึก/ }));
    await waitFor(() =>
      expect(mockAgencies.find((a) => a.id === ACTIVE_ID)!.endpoint_url).toBe(
        "https://rd-new.example/api/chat",
      ),
    );
  });
});

describe("RoutingTab", () => {
  it("saves routing fields", async () => {
    const user = userEvent.setup();
    render(wrap(<RoutingTab agency={activeAgency()} />));
    const hint = screen.getByLabelText(/Router hint/);
    await user.clear(hint);
    await user.type(hint, "ภาษีทุกชนิด");
    const priority = screen.getByLabelText(/Priority/);
    await user.clear(priority);
    await user.type(priority, "5");
    await user.click(screen.getByRole("button", { name: /บันทึก/ }));
    await waitFor(() => {
      const row = mockAgencies.find((a) => a.id === ACTIVE_ID)!;
      expect(row.router_hint).toBe("ภาษีทุกชนิด");
      expect(row.priority).toBe(5);
    });
  });

  it("edits data scope", async () => {
    const user = userEvent.setup();
    render(wrap(<RoutingTab agency={activeAgency()} />));
    await user.type(screen.getByPlaceholderText(/เพิ่มขอบเขตข้อมูล/), "ภาษีมูลค่าเพิ่ม");
    await user.click(screen.getByRole("button", { name: "เพิ่มขอบเขต" }));
    await user.click(screen.getByRole("button", { name: /บันทึก/ }));
    await waitFor(() =>
      expect(mockAgencies.find((a) => a.id === ACTIVE_ID)!.data_scope).toContain("ภาษีมูลค่าเพิ่ม"),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/detail/editTabs.test.tsx`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement ConnectionTab**

Create `frontend/src/features/agencies/detail/ConnectionTab.tsx`:

```tsx
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";
import type { Agency, ApiHeader } from "@/shared/types/agency";

import { parseExpectedPayload } from "../agencyForm";
import { useUpdateAgency } from "../useAgencies";
import { HeadersEditor } from "../wizard/HeadersEditor";

export function ConnectionTab({ agency }: { agency: Agency }) {
  const updateMutation = useUpdateAgency();
  const [endpointUrl, setEndpointUrl] = useState(agency.endpointUrl ?? "");
  const [apiHeaders, setApiHeaders] = useState<ApiHeader[]>(agency.apiHeaders ?? []);
  const [payloadRaw, setPayloadRaw] = useState(
    agency.expectedPayload ? JSON.stringify(agency.expectedPayload, null, 2) : "",
  );
  const [mcpToolName, setMcpToolName] = useState(agency.mcpToolName ?? "");

  const { value: parsedPayload, error: payloadError } = parseExpectedPayload(payloadRaw);

  const save = async () => {
    try {
      await updateMutation.mutateAsync({
        id: agency.id,
        endpointUrl,
        apiHeaders: apiHeaders.filter((h) => h.name && h.value),
        expectedPayload: parsedPayload,
        mcpToolName: mcpToolName || null,
      });
      toast.success("บันทึกการเชื่อมต่อสำเร็จ");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
    }
  };

  return (
    <div className="space-y-5 max-w-lg">
      <div className="space-y-1.5">
        <Label htmlFor="conn-endpoint">Endpoint URL</Label>
        <Input id="conn-endpoint" value={endpointUrl} onChange={(e) => setEndpointUrl(e.target.value)} />
      </div>

      {agency.connectionType === "API" && (
        <>
          <div className="space-y-1.5">
            <Label>Headers</Label>
            <HeadersEditor headers={apiHeaders} onChange={setApiHeaders} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="conn-payload">Expected payload (JSON template)</Label>
            <Textarea
              id="conn-payload"
              rows={5}
              value={payloadRaw}
              onChange={(e) => setPayloadRaw(e.target.value)}
              className="font-mono text-xs"
            />
            {payloadError && <p className="text-xs text-destructive">JSON ไม่ถูกต้อง</p>}
          </div>
        </>
      )}

      {agency.connectionType === "MCP" && (
        <div className="space-y-1.5">
          <Label htmlFor="conn-tool">MCP tool</Label>
          <Input id="conn-tool" value={mcpToolName} onChange={(e) => setMcpToolName(e.target.value)} className="font-mono" />
        </div>
      )}

      <Button onClick={save} disabled={updateMutation.isPending || payloadError}>
        {updateMutation.isPending ? "กำลังบันทึก…" : "บันทึก"}
      </Button>
    </div>
  );
}
```

- [ ] **Step 4: Implement RoutingTab**

Create `frontend/src/features/agencies/detail/RoutingTab.tsx`:

```tsx
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Textarea } from "@/shared/components/ui/textarea";
import type { Agency } from "@/shared/types/agency";

import { DataScopeEditor } from "../DataScopeEditor";
import { useUpdateAgency } from "../useAgencies";

function parseIntOrNull(raw: string): number | null {
  const n = raw.trim() ? parseInt(raw, 10) : NaN;
  return Number.isNaN(n) ? null : n;
}

export function RoutingTab({ agency }: { agency: Agency }) {
  const updateMutation = useUpdateAgency();
  const [dataScope, setDataScope] = useState<string[]>(agency.dataScope);
  const [routerHint, setRouterHint] = useState(agency.routerHint);
  const [priority, setPriority] = useState(agency.priority != null ? String(agency.priority) : "");
  const [timeoutS, setTimeoutS] = useState(
    agency.dispatchTimeoutS != null ? String(agency.dispatchTimeoutS) : "",
  );
  const [rateLimit, setRateLimit] = useState(
    agency.rateLimitRpm != null ? String(agency.rateLimitRpm) : "",
  );

  const save = async () => {
    try {
      await updateMutation.mutateAsync({
        id: agency.id,
        dataScope,
        routerHint,
        priority: parseIntOrNull(priority),
        dispatchTimeoutS: parseIntOrNull(timeoutS),
        rateLimitRpm: parseIntOrNull(rateLimit),
      });
      toast.success("บันทึก routing สำเร็จ");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "เกิดข้อผิดพลาด");
    }
  };

  return (
    <div className="space-y-5 max-w-lg">
      <div className="space-y-1.5">
        <Label>ขอบเขตข้อมูล (data scope)</Label>
        <DataScopeEditor scope={dataScope} onChange={setDataScope} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="rt-hint">Router hint</Label>
        <Textarea id="rt-hint" rows={3} value={routerHint} onChange={(e) => setRouterHint(e.target.value)} />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="rt-priority">Priority</Label>
          <Input id="rt-priority" type="number" min={1} value={priority} onChange={(e) => setPriority(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="rt-timeout">Timeout (วินาที)</Label>
          <Input id="rt-timeout" type="number" min={1} value={timeoutS} onChange={(e) => setTimeoutS(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="rt-rpm">Rate limit (rpm)</Label>
          <Input id="rt-rpm" type="number" min={1} value={rateLimit} onChange={(e) => setRateLimit(e.target.value)} />
        </div>
      </div>
      <Button onClick={save} disabled={updateMutation.isPending}>
        {updateMutation.isPending ? "กำลังบันทึก…" : "บันทึก"}
      </Button>
    </div>
  );
}
```

Note: `useUpdateAgency` sends every key in its payload including `undefined` for fields not passed — verify the existing `mutationFn` omits `undefined` keys (axios drops `undefined` in JSON serialization, so a partial update is safe as-is).

- [ ] **Step 5: Swap the placeholders**

In `detail/AgencyDetailPage.tsx`:

```tsx
        <TabsContent value="connection">
          <ConnectionTab agency={agency} />
        </TabsContent>
        <TabsContent value="routing">
          <RoutingTab agency={agency} />
        </TabsContent>
```

Add imports for `ConnectionTab`, `RoutingTab`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd frontend && rtk pnpm vitest run src/features/agencies/detail/`
Expected: PASS.

- [ ] **Step 7: Lint and commit**

```bash
cd frontend && rtk pnpm lint
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add frontend/src/features/agencies/detail
rtk git commit -m "feat(agencies): add inline-editable connection and routing tabs"
```

---

### Task 15: Delete the dialog-era components

**Files:**
- Delete: `frontend/src/features/agencies/AgencyFormDialog.tsx`
- Delete: `frontend/src/features/agencies/AgencyApiFields.tsx`
- Delete: `frontend/src/features/agencies/AgencyHeadersEditor.tsx`
- Delete: `frontend/src/features/agencies/AgencyInfoTab.tsx`
- Delete: `frontend/src/features/agencies/AgencyDetailHeader.tsx`
- Delete: `frontend/src/features/agencies/AgencyDetailStats.tsx`
- Delete: `frontend/src/features/agencies/AgencyStatsTab.tsx`
- Delete: `frontend/src/features/agencies/AgencyDetailPage.tsx` (old; replaced by `detail/AgencyDetailPage.tsx`)
- Modify: `frontend/src/features/agencies/agencyForm.ts` (remove now-dead exports)

- [ ] **Step 1: Verify nothing references the dead files**

Run: `cd frontend && rtk grep -rn "AgencyFormDialog\|AgencyApiFields\|AgencyHeadersEditor\|AgencyInfoTab\|AgencyDetailHeader\|AgencyDetailStats\|AgencyStatsTab" src --include="*.tsx" --include="*.ts"`
Expected: matches ONLY inside the files being deleted. Also confirm the only `AgencyDetailPage` import in `App.tsx` points at `detail/AgencyDetailPage`. If anything else matches, fix the reference first.

- [ ] **Step 2: Delete**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide/frontend/src/features/agencies
rtk git rm AgencyFormDialog.tsx AgencyApiFields.tsx AgencyHeadersEditor.tsx AgencyInfoTab.tsx AgencyDetailHeader.tsx AgencyDetailStats.tsx AgencyStatsTab.tsx AgencyDetailPage.tsx
```

- [ ] **Step 3: Remove dead exports from agencyForm.ts**

The dialog was the only consumer of `isFormValid`, `ParsedSpec`, and `ParseSpecResponse`. Check with:

Run: `cd frontend && rtk grep -rn "isFormValid\|ParsedSpec\|ParseSpecResponse" src`
Delete whichever of those exports (and their tests in `agencyForm.test.ts`) have no remaining non-test consumers. Keep everything the wizard/tabs use (`agencyToFormState`, `buildSavePayload`, `parseExpectedPayload`, `PROTOCOL_INFO`, step validators).

- [ ] **Step 4: Full test suite + lint must stay green**

Run: `cd frontend && rtk pnpm test && rtk pnpm lint`
Expected: all tests pass, no lint errors.

- [ ] **Step 5: Commit**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add -A frontend/src/features/agencies
rtk git commit -m "refactor(agencies): remove dialog-era components replaced by wizard and detail tabs"
```

---

### Task 16: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `cd frontend && rtk pnpm test`
Expected: ALL tests pass (existing chat/users tests + every new agencies test).

- [ ] **Step 2: Type-check via production build**

Run: `cd frontend && rtk pnpm build`
Expected: build succeeds with zero TS errors. (This is the only full-project type check — vitest does not type-check non-imported files.)

- [ ] **Step 3: Lint**

Run: `cd frontend && rtk pnpm lint`
Expected: clean.

- [ ] **Step 4: Manual smoke test with mocks**

```bash
cd frontend && VITE_USE_MOCKS=true rtk pnpm dev
```

Then in the app (login against the real backend — only agency endpoints are mocked):
1. `/agencies` shows 5 fixture tiles with health bars; filters and search work.
2. "เพิ่มหน่วยงาน" → complete the wizard for an API agency → lands on detail page, Active.
3. Draft tile "ตั้งค่าต่อ" → wizard resumes at connection step.
4. Detail page: Health tab charts render for 24h/7d/30d; status dropdown moves Active → ปิดปรับปรุง; Routing tab saves.

- [ ] **Step 5: Verify nothing references VITE_USE_MOCKS in production paths**

Run: `cd frontend && rtk grep -rn "VITE_USE_MOCKS" src`
Expected: only `src/main.tsx`.

- [ ] **Step 6: Commit any final fixes and update the plan checkboxes**

```bash
cd /mnt/c/Users/foo/thai-citizen-guide
rtk git add -A && rtk git commit -m "chore(agencies): final verification fixes" || echo "nothing to fix"
```

---

## Out of Scope (backend sub-project 2)

- FastAPI: 4-state lifecycle + migration, MCP/A2A health checks, history aggregation endpoint, `/status` transition endpoint, `/mcp/discover`, router use of priority/hint/timeout/scope.
- The MSW fixtures in `src/mocks/` are the contract reference for that work.
