import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProtectedRoute } from "./ProtectedRoute";

const auth = { user: null as { role: string } | null, isAdmin: false, isLoading: false };
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));

function renderAt(initial: string, ui: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route path="/chat" element={<div>chat page</div>} />
        <Route path="/secret" element={ui} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute requireNonBasic", () => {
  beforeEach(() => {
    auth.user = { role: "user" };
    auth.isAdmin = false;
    auth.isLoading = false;
  });

  it("redirects a basic user to /chat", () => {
    renderAt("/secret", <ProtectedRoute requireNonBasic><div>secret content</div></ProtectedRoute>);
    expect(screen.getByText("chat page")).toBeInTheDocument();
    expect(screen.queryByText("secret content")).not.toBeInTheDocument();
  });

  it("lets an admin through", () => {
    auth.user = { role: "admin" };
    auth.isAdmin = true;
    renderAt("/secret", <ProtectedRoute requireNonBasic><div>secret content</div></ProtectedRoute>);
    expect(screen.getByText("secret content")).toBeInTheDocument();
  });

  it("does not gate routes without requireNonBasic", () => {
    renderAt("/secret", <ProtectedRoute><div>secret content</div></ProtectedRoute>);
    expect(screen.getByText("secret content")).toBeInTheDocument();
  });
});
