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
