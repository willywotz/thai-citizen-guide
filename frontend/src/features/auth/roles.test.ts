import { describe, expect, it } from "vitest";
import { ROUTE_ROLES, canAccess, type Role } from "./roles";

const ROLES: Role[] = ["user", "admin"];

describe("canAccess", () => {
  it("lets every role reach chat and architecture", () => {
    for (const role of ROLES) {
      expect(canAccess(role, "/chat")).toBe(true);
      expect(canAccess(role, "/architecture")).toBe(true);
    }
  });

  it("restricts every other known route to admin", () => {
    for (const [path, allowed] of Object.entries(ROUTE_ROLES)) {
      if (path === "/chat" || path === "/architecture") continue;
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
