import { config } from "dotenv";

config({ path: ".env.test" });

import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";

const { adminApi, login } = await import("../blackbox/src/helpers/auth");
const { ensureRoleUsers, seedDefaults, ensureAgencyOwner } = await import(
  "../blackbox/src/helpers/provision"
);
const { ROLES, ROLE_ACCOUNTS } = await import("../blackbox/src/access-matrix");

export default async function globalSetup(): Promise<void> {
  const admin = await adminApi();
  await seedDefaults(admin);
  await ensureRoleUsers(admin);
  await ensureAgencyOwner(admin);

  mkdirSync(".auth", { recursive: true });
  const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:8080";
  const password = process.env.TEST_USER_PASSWORD ?? "blackbox1234";

  for (const role of ROLES) {
    const token = await login(ROLE_ACCOUNTS[role].email, password);
    const browser = await chromium.launch();
    const ctx = await browser.newContext({ baseURL });
    const page = await ctx.newPage();
    await page.addInitScript((t) => {
      window.localStorage.setItem("auth_token", t as string);
    }, token);
    await page.goto(baseURL);
    await ctx.storageState({ path: `.auth/${role}.json` });
    await browser.close();
  }
}
