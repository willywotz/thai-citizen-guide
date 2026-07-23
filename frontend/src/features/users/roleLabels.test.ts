import { describe, expect, it } from "vitest";
import { ROLE_LABEL, ROLE_ORDER } from "./roleLabels";

describe("role labels", () => {
  it("labels both surviving roles", () => {
    expect(ROLE_ORDER).toEqual(["user", "admin"]);
    expect(ROLE_LABEL.user).toBe("ผู้ใช้");
    expect(ROLE_LABEL.admin).toBe("ผู้ดูแลระบบ");
  });

  it("has no label for removed roles", () => {
    expect(Object.keys(ROLE_LABEL)).toHaveLength(2);
  });
});
