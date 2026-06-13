import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    globalSetup: ["./global-setup.ts"],
    testTimeout: 30000,
    hookTimeout: 30000,
  },
});
