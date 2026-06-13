import { defineConfig } from "@playwright/test";
import { config } from "dotenv";

config({ path: ".env.test" });

export default defineConfig({
  testDir: "./tests",
  globalSetup: "./global-setup.ts",
  timeout: 30000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "on-first-retry",
  },
});
