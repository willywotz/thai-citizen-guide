import { describe, expect, it } from "vitest";
import { ROUTE_ROLES, canAccess, type Role } from "./roles";

const ROLES: Role[] = ["user", "admin"];

const READ_ONLY_ROUTES = ["/dashboard", "/executive", "/health", "/heatmap", "/feedback", "/usage"];

describe("canAccess", () => {
  it("lets every role reach chat and architecture", () => {
    for (const role of ROLES) {
      expect(canAccess(role, "/chat")).toBe(true);
      expect(canAccess(role, "/architecture")).toBe(true);
    }
  });

  it("lets every role reach the read-only operational pages", () => {
    for (const path of READ_ONLY_ROUTES) {
      expect(canAccess("user", path)).toBe(true);
      expect(canAccess("admin", path)).toBe(true);
    }
  });

  it("restricts every other known route to admin", () => {
    for (const [path, allowed] of Object.entries(ROUTE_ROLES)) {
      if (path === "/chat" || path === "/architecture" || READ_ONLY_ROUTES.includes(path)) continue;
      expect(allowed).toEqual(["admin"]);
      expect(canAccess("user", path)).toBe(false);
      expect(canAccess("admin", path)).toBe(true);
    }
  });

  it("allows unknown paths through — routing owns those", () => {
    expect(canAccess("user", "/not-a-known-route")).toBe(true);
  });

  it("no longer routes to removed owner pages", () => {
    expect(ROUTE_ROLES["/my-agencies"]).toBeUndefined();
  });
});
