import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppSidebar } from "./AppSidebar";
import { SidebarProvider } from "@/shared/components/ui/sidebar";
import type { AuthUser } from "@/features/auth/useAuth";

const auth: { user: AuthUser | null; isReadOnly: boolean; signOut: () => void } = {
  user: null,
  isReadOnly: false,
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

  it("shows only chat + architecture for a basic user", () => {
    auth.user = { ...auth.user!, role: "user" };
    renderSidebar();
    expect(screen.getByText("แชท")).toBeInTheDocument();
    expect(screen.getByText("Architecture")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
  });

  it("shows analytics pages but not management for a viewer", () => {
    auth.user = { ...auth.user!, role: "viewer" };
    renderSidebar();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("การใช้งาน API Key")).toBeInTheDocument(); // usage
    expect(screen.queryByText("จัดการหน่วยงาน")).not.toBeInTheDocument(); // agencies mgmt
    expect(screen.queryByText("จัดการผู้ใช้")).not.toBeInTheDocument(); // users
  });

  it("shows users + audit-log for an auditor but not settings", () => {
    auth.user = { ...auth.user!, role: "auditor" };
    renderSidebar();
    expect(screen.getByText("จัดการผู้ใช้")).toBeInTheDocument();
    expect(screen.getByText("บันทึกการตรวจสอบ")).toBeInTheDocument();
    expect(screen.queryByText("ตั้งค่าระบบ")).not.toBeInTheDocument();
  });
});
