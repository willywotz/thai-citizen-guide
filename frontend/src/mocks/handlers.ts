import { http, HttpResponse } from "msw";

import { LEGAL_TRANSITIONS } from "@/features/agencies/lifecycle";
import type { AgencyLifecycleStatus, AgencyRow, HealthWindow } from "@/shared/types/agency";
import { agencyUsageData, categoryData, dashboardStats, weeklyTrendData } from "@/shared/data/mockData";

import { FIXTURE_MCP_TOOLS, makeHistory, mockAgencies, mockFeedbackStats, row } from "./fixtures";

const MOCK_AGENCY_HEALTH = {
  agencies: [
    { id: "rd", name: "กรมสรรพากร", shortName: "RD", status: "healthy", uptime: 99.2, currentLatency: 320, avgLatency: 310, errorRate: 0.1, requestsPerMin: 42, lastCheckedAt: "2026-06-23T08:00:00Z" },
    { id: "fda", name: "สำนักงานอาหารและยา", shortName: "อย.", status: "degraded", uptime: 71.0, currentLatency: 1230, avgLatency: 1100, errorRate: 2.4, requestsPerMin: 12, lastCheckedAt: "2026-06-23T08:00:00Z" },
  ],
  historical: [
    { time: "00:00", rd_latency: 310, fda_latency: 1100 },
    { time: "01:00", rd_latency: 290, fda_latency: 1200 },
  ],
  incidents: [],
  slaCompliance: [
    { agency: "กรมสรรพากร", uptime: 99.2, target: 99.0, met: true },
  ],
  generatedAt: "2026-06-23T08:00:00Z",
};

const MOCK_HEATMAP = {
  range: "7d" as const,
  days: 7,
  sampleSize: 1000,
  totalMessages: 5000,
  days_labels: ["จ", "อ", "พ", "พฤ", "ศ", "ส", "อา"],
  hours: Array.from({ length: 24 }, (_, i) => i),
  agencies: [{ id: "rd", name: "กรมสรรพากร" }],
  hourlyByAgency: [{ agency: "กรมสรรพากร", agencyId: "rd", data: Array(24).fill(10) }],
  dayHourMatrix: [{ day: "จ", dayIndex: 1, data: Array(24).fill(5) }],
  insights: {
    peakDay: "พุธ",
    peakHour: "10:00",
    peakValue: 150,
    totalRequests: 1000,
    businessHoursPercent: 80,
    busiest: { agency: "กรมสรรพากร", total: 500, peakHour: 10 },
    recommendation: "เพิ่มทรัพยากรช่วง 09-11 น.",
  },
  generatedAt: "2026-06-23T08:00:00Z",
};

function findAgency(id: string): AgencyRow | undefined {
  return mockAgencies.find((a) => a.id === id);
}

export const handlers = [
  http.get("*/api/v1/agency-health", () => HttpResponse.json(MOCK_AGENCY_HEALTH)),

  http.get("*/api/v1/usage-heatmap", () => HttpResponse.json(MOCK_HEATMAP)),

  http.get("*/api/v1/dashboard/stats", () =>
    HttpResponse.json({
      success: true,
      data: { stats: dashboardStats, agencyUsage: agencyUsageData, weeklyTrend: weeklyTrendData, categoryData },
      responseTime: 42,
    }),
  ),

  http.get("*/api/v1/insight/usage", () =>
    HttpResponse.json([
      { key: "claude-3-5-sonnet", prompt_tokens: 10000, completion_tokens: 2000, cost_usd: 0.036 },
    ]),
  ),

  http.get("*/api/v1/feedback/stats", () => HttpResponse.json(mockFeedbackStats)),

  http.patch("*/api/v1/messages/:id/rating", ({ params }) =>
    HttpResponse.json({ success: true, messageId: params.id }),
  ),

  http.get("*/api/v1/agencies", () =>
    HttpResponse.json({ data: mockAgencies, total: mockAgencies.length }),
  ),

  http.get("*/api/v1/agencies/:id/health/history", ({ params, request }) => {
    const agency = findAgency(params.id as string);
    if (!agency) return HttpResponse.json({ detail: "Agency not found" }, { status: 404 });
    const url = new URL(request.url);
    const window = (url.searchParams.get("window") ?? "24h") as HealthWindow;
    if (!["24h", "7d", "30d"].includes(window)) {
      return HttpResponse.json({ detail: "invalid window" }, { status: 422 });
    }
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
    const created = row({
      ...body,
      id: crypto.randomUUID(),
      name: body.name ?? "",
      short_name: body.short_name ?? "",
      status: body.status ?? "draft",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
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
        { step: 1, label: "DNS lookup", status: "done", time: 12 },
        { step: 2, label: "Handshake", status: "done", time: 120 },
      ],
      latency: "320ms",
    });
  }),
];
