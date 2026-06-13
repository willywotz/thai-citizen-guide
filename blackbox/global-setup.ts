import { config } from "dotenv";

config({ path: ".env.test" });

const { adminApi } = await import("./src/helpers/auth");
const { ensureRoleUsers, seedDefaults } = await import("./src/helpers/provision");

export async function setup(): Promise<void> {
  const admin = await adminApi();
  await seedDefaults(admin);
  await ensureRoleUsers(admin);
}
