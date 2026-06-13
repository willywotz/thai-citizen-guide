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

function unwrap<T>(data: T[] | { data: T[] }): T[] {
  return Array.isArray(data) ? data : data.data;
}

// Make bb-agency-owner own the first seeded agency so its owner-scoped detail
// pages (e.g. low-rated feedback) have a real, owned resource to read. Idempotent:
// the backend grant uses get_or_create, so re-running is a no-op.
export async function ensureAgencyOwner(admin: AxiosInstance): Promise<string | undefined> {
  const agencies = await admin.get("/api/v1/agencies");
  const agencyId = unwrap<{ id: string }>(agencies.data)?.[0]?.id;
  if (!agencyId) {
    throw new Error("ensureAgencyOwner: no seeded agency to assign ownership of");
  }
  const users = await admin.get("/api/v1/users");
  const owner = unwrap<{ id: string; email: string }>(users.data).find(
    (u) => u.email === ROLE_ACCOUNTS.agency_owner.email,
  );
  if (!owner) {
    throw new Error("ensureAgencyOwner: bb-agency-owner user not found");
  }
  const resp = await admin.post(`/api/v1/agencies/${agencyId}/owners`, { user_id: owner.id });
  if (![200, 201].includes(resp.status)) {
    throw new Error(`ensureAgencyOwner: assign failed: ${resp.status} ${JSON.stringify(resp.data)}`);
  }
  return agencyId;
}
