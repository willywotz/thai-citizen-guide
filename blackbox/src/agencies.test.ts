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
