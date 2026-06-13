import { describe, expect, it } from "vitest";
import { ROLE_LABEL, ROLE_ORDER } from "./roleLabels";

describe("ROLE_LABEL", () => {
  it("has a Thai label for every role", () => {
    expect(ROLE_LABEL.user).toBe("ผู้ใช้");
    expect(ROLE_LABEL.viewer).toBe("ผู้บริหาร");
    expect(ROLE_LABEL.auditor).toBe("ผู้ตรวจสอบ");
    expect(ROLE_LABEL.agency_owner).toBe("เจ้าของหน่วยงาน");
    expect(ROLE_LABEL.admin).toBe("ผู้ดูแลระบบ");
  });

  it("orders roles from least to most privileged", () => {
    expect(ROLE_ORDER).toEqual(["user", "viewer", "auditor", "agency_owner", "admin"]);
  });
});
