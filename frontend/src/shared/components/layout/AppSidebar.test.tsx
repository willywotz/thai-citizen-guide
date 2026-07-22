import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppSidebar } from "./AppSidebar";
import { SidebarProvider } from "@/shared/components/ui/sidebar";
import type { AuthUser } from "@/features/auth/useAuth";

const auth: { user: AuthUser | null; signOut: () => void } = {
  user: null,
  signOut: () => {},
};
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));
vi.mock("@/features/agencies/useAgencies", () => ({ useAgencies: () => ({ data: [] }) }));

function renderSidebar() {
  return render(
    <MemoryRouter>
      <SidebarProvider>
        <AppSidebar />
      </SidebarProvider>
    </MemoryRouter>,
  );
}

describe("AppSidebar visibility", () => {
  beforeEach(() => {
    auth.user = { id: "1", email: "u@x.com", displayName: "U", role: "user", avatarUrl: null };
  });

  it("shows read-only operational pages but not admin-only pages for a basic user", () => {
    auth.user = { ...auth.user!, role: "user" };
    renderSidebar();
    expect(screen.getByText("แชท")).toBeInTheDocument();
    expect(screen.getByText("Architecture")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.queryByText("จัดการหน่วยงาน")).not.toBeInTheDocument();
  });

  it("shows every nav item for an admin", () => {
    auth.user = { ...auth.user!, role: "admin" };
    renderSidebar();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("จัดการหน่วยงาน")).toBeInTheDocument();
    expect(screen.getByText("จัดการผู้ใช้")).toBeInTheDocument();
    expect(screen.getByText("บันทึกการตรวจสอบ")).toBeInTheDocument();
    expect(screen.getByText("ตั้งค่าระบบ")).toBeInTheDocument();
  });

  it("no longer shows the removed my-agencies nav item", () => {
    auth.user = { ...auth.user!, role: "admin" };
    renderSidebar();
    expect(screen.queryByText("หน่วยงานของฉัน")).not.toBeInTheDocument();
  });
});
