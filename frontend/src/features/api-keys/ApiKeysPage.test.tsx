import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ApiKeysPage from "./ApiKeysPage";

const auth = { isReadOnly: false };
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));
vi.mock("@/features/api-keys/apiKeyApi", () => ({
  listAPIKeys: () => Promise.resolve([]),
  createAPIKey: vi.fn(),
  updateAPIKey: vi.fn(),
  revokeAPIKey: vi.fn(),
  deleteAPIKey: vi.fn(),
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ApiKeysPage />
    </QueryClientProvider>,
  );
}

describe("ApiKeysPage create button", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
  });

  it("shows the create button for a writer", async () => {
    renderPage();
    expect(await screen.findByText("สร้าง API Key")).toBeInTheDocument();
  });

  it("hides the create button for a read-only role", () => {
    auth.isReadOnly = true;
    renderPage();
    expect(screen.queryByText("สร้าง API Key")).not.toBeInTheDocument();
  });
});
