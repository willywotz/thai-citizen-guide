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
