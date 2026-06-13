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
