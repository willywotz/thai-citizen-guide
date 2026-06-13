import type { AxiosInstance } from "axios";
import { ROLES, ROLE_ACCOUNTS } from "../access-matrix";

// Create one user per role, tolerating accounts that already exist.
export async function ensureRoleUsers(admin: AxiosInstance): Promise<void> {
  const password = process.env.TEST_USER_PASSWORD ?? "blackbox1234";
  for (const role of ROLES) {
    const { email } = ROLE_ACCOUNTS[role];
    const resp = await admin.post("/api/v1/users", {
      email,
      role,
      display_name: `Blackbox ${role}`,
      password,
    });
    // 200/201 created; 400/409 already exists — both acceptable.
    if (![200, 201, 400, 409].includes(resp.status)) {
      throw new Error(`failed to ensure user ${email}: ${resp.status} ${JSON.stringify(resp.data)}`);
    }
  }
}

// Seed default agencies (and admin, which is skipped if present) so reads have data.
export async function seedDefaults(admin: AxiosInstance): Promise<void> {
  await admin.post("/api/v1/seed/all", {});
}
