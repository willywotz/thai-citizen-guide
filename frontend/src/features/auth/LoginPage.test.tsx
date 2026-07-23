import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "./LoginPage";

vi.mock("@/features/auth/useAuth", () => ({
  useAuth: () => ({ user: null, isAdmin: false, isLoading: false, setAuth: vi.fn() }),
}));

describe("LoginPage", () => {
  it("does not link to the removed signup page", () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("link", { name: /สมัครสมาชิก/ })).not.toBeInTheDocument();
  });
});
