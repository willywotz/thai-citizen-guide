import { describe, expect, it } from "vitest";
import { ROUTE_ROLES, READ_ONLY_ROLES, canAccess } from "./roles";

describe("role map", () => {
  it("lets every authenticated role reach chat + architecture", () => {
    for (const r of ["user", "viewer", "auditor", "agency_owner", "admin"] as const) {
      expect(canAccess(r, "/chat")).toBe(true);
      expect(canAccess(r, "/architecture")).toBe(true);
    }
  });

  it("scopes viewer to analytics pages, not management", () => {
    expect(canAccess("viewer", "/dashboard")).toBe(true);
    expect(canAccess("viewer", "/usage")).toBe(true);
    expect(canAccess("viewer", "/agencies")).toBe(false);
    expect(canAccess("viewer", "/users")).toBe(false);
  });

  it("lets auditor reach everything except settings + owner-only pages", () => {
    expect(canAccess("auditor", "/users")).toBe(true);
    expect(canAccess("auditor", "/audit-log")).toBe(true);
    expect(canAccess("auditor", "/agencies")).toBe(true);
    expect(canAccess("auditor", "/settings")).toBe(false);
    expect(canAccess("auditor", "/my-agencies")).toBe(false);
    expect(canAccess("auditor", "/agencies/new")).toBe(false);
  });

  it("marks viewer and auditor as read-only", () => {
    expect(READ_ONLY_ROLES).toContain("viewer");
    expect(READ_ONLY_ROLES).toContain("auditor");
    expect(READ_ONLY_ROLES).not.toContain("agency_owner");
    expect(READ_ONLY_ROLES).not.toContain("admin");
  });

  it("allows unknown paths by default", () => {
    expect(canAccess("user", "/some/unknown/path")).toBe(true);
  });
});
