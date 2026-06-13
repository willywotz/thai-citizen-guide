import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UsersPage from "./UsersPage";

const auth = { isReadOnly: false };
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));
vi.mock("./userApi", () => ({
  listUsers: () => Promise.resolve([]),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deactivateUser: vi.fn(),
  activateUser: vi.fn(),
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <UsersPage />
    </QueryClientProvider>,
  );
}

describe("UsersPage create control", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
  });

  it("shows the add-user button for a writer (admin)", async () => {
    renderPage();
    expect(await screen.findByText("เพิ่มผู้ใช้")).toBeInTheDocument();
  });

  it("hides the add-user button for a read-only role (auditor)", () => {
    auth.isReadOnly = true;
    renderPage();
    expect(screen.queryByText("เพิ่มผู้ใช้")).not.toBeInTheDocument();
  });
});
