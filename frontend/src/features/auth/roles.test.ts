import { describe, expect, it } from "vitest";
import { ROUTE_ROLES, canAccess, type Role } from "./roles";

const ROLES: Role[] = ["user", "admin"];

const READ_ONLY_ROUTES = ["/dashboard", "/executive", "/health", "/heatmap", "/feedback", "/usage"];

/** Reachable by `user` but not read-only: they may delete their own conversations. */
const OWN_DATA_ROUTES = ["/history"];

const USER_ROUTES = [...READ_ONLY_ROUTES, ...OWN_DATA_ROUTES];

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

  it("lets every role reach their own conversation history", () => {
    for (const path of OWN_DATA_ROUTES) {
      expect(canAccess("user", path)).toBe(true);
      expect(canAccess("admin", path)).toBe(true);
    }
  });

  it("restricts every other known route to admin", () => {
    for (const [path, allowed] of Object.entries(ROUTE_ROLES)) {
      if (
        path === "/chat" ||
        path === "/architecture" ||
        USER_ROUTES.includes(path) ||
        path === "/settings" ||
        path === "/settings/usage"
      )
        continue;
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

  it("restricts the merged llm-settings page to admin", () => {
    expect(canAccess("user", "/llm-settings")).toBe(false);
    expect(canAccess("admin", "/llm-settings")).toBe(true);
  });
});

describe("settings route roles", () => {
  it("lets every role reach the settings area (holds the all-roles Usage tab)", () => {
    expect(canAccess("user", "/settings")).toBe(true);
    expect(canAccess("admin", "/settings")).toBe(true);
  });

  it("lets every role reach the Usage tab", () => {
    expect(canAccess("user", "/settings/usage")).toBe(true);
  });

  it("restricts the admin-only tabs to admins", () => {
    for (const path of [
      "/settings/system",
      "/settings/llm",
      "/settings/api-keys",
      "/settings/connections",
      "/settings/audit",
    ]) {
      expect(canAccess("user", path)).toBe(false);
      expect(canAccess("admin", path)).toBe(true);
    }
  });
});
