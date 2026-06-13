import { test, expect } from "@playwright/test";
import { ROLES, PAGE_MATRIX } from "../../blackbox/src/access-matrix";

// Pages every authenticated role may see; visiting them is never a redirect failure.
const ALWAYS_ALLOWED = new Set(["/chat", "/architecture"]);

for (const role of ROLES) {
  const pages = PAGE_MATRIX.filter((p) => p.roles.includes(role));

  test.describe(`${role} page access`, () => {
    test.use({ storageState: `.auth/${role}.json` });

    for (const p of pages) {
      test(`${role} can open ${p.path}`, async ({ page }) => {
        const denied: string[] = [];
        page.on("response", (resp) => {
          if (resp.url().includes("/api/") && [401, 403].includes(resp.status())) {
            denied.push(`${resp.status()} ${resp.url()}`);
          }
        });

        await page.goto(p.path);
        await page.waitForLoadState("networkidle");

        // Guard must not bounce an entitled role back to /chat.
        if (!ALWAYS_ALLOWED.has(p.path)) {
          expect(page.url(), `${role} was redirected away from ${p.path}`).not.toMatch(/\/chat(\?|$)/);
        }

        expect(denied, `401/403 calls on ${p.path}:\n${denied.join("\n")}`).toHaveLength(0);
      });
    }
  });
}
