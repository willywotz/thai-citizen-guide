import { http, HttpResponse } from "msw";

import { LEGAL_TRANSITIONS } from "@/features/agencies/lifecycle";
import type { AgencyLifecycleStatus, AgencyRow, HealthWindow } from "@/shared/types/agency";

import { FIXTURE_MCP_TOOLS, makeHistory, mockAgencies } from "./fixtures";

function findAgency(id: string): AgencyRow | undefined {
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
