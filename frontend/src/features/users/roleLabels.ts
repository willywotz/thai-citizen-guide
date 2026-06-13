import type { UserRole } from "./userApi";

/** Short Thai labels for each role — used by the users table badge and role filter. */
export const ROLE_LABEL: Record<UserRole, string> = {
  user: "ผู้ใช้",
  viewer: "ผู้บริหาร",
  auditor: "ผู้ตรวจสอบ",
  agency_owner: "เจ้าของหน่วยงาน",
  admin: "ผู้ดูแลระบบ",
};

/** Roles ordered from least to most privileged, for stable dropdown ordering. */
export const ROLE_ORDER: UserRole[] = ["user", "viewer", "auditor", "agency_owner", "admin"];
