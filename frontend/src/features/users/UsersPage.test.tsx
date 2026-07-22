import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import UsersPage from "./UsersPage";

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
  it("shows the add-user button for a writer (admin)", async () => {
    renderPage();
    expect(await screen.findByText("เพิ่มผู้ใช้")).toBeInTheDocument();
  });

  it("renders the role filter defaulting to all roles", async () => {
    renderPage();
    expect(await screen.findByText("บทบาททั้งหมด")).toBeInTheDocument();
  });
});
