import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { mockAgencies, resetMockData } from "@/mocks/fixtures";
import { mapRowToAgency } from "@/shared/types/agency";

import { ConnectionTab } from "./ConnectionTab";
import { RoutingTab } from "./RoutingTab";

afterEach(() => {
  resetMockData();
});

const ACTIVE_ID = "11111111-1111-1111-1111-111111111111";

function wrap(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function activeAgency() {
  return mapRowToAgency(mockAgencies.find((a) => a.id === ACTIVE_ID)!);
}

describe("ConnectionTab", () => {
  it("saves an edited endpoint", async () => {
    const user = userEvent.setup();
    render(wrap(<ConnectionTab agency={activeAgency()} />));
    const input = screen.getByLabelText("Endpoint URL");
    await user.clear(input);
    await user.type(input, "https://rd-new.example/api/chat");
    await user.click(screen.getByRole("button", { name: /บันทึก/ }));
    await waitFor(() =>
      expect(mockAgencies.find((a) => a.id === ACTIVE_ID)!.endpoint_url).toBe(
        "https://rd-new.example/api/chat",
      ),
    );
  });

  it("shows wizard-style gray placeholders for empty connection fields", () => {
    render(wrap(<ConnectionTab agency={activeAgency()} />));
    expect(screen.getByPlaceholderText("https://…")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/"query": "__query__"/)).toBeInTheDocument();
  });
});

describe("RoutingTab", () => {
  it("saves routing fields", async () => {
    const user = userEvent.setup();
    render(wrap(<RoutingTab agency={activeAgency()} />));
    const hint = screen.getByLabelText(/Router hint/);
    await user.clear(hint);
    await user.type(hint, "ภาษีทุกชนิด");
    const priority = screen.getByLabelText(/Priority/);
    await user.clear(priority);
    await user.type(priority, "5");
    await user.click(screen.getByRole("button", { name: /บันทึก/ }));
    await waitFor(() => {
      const row = mockAgencies.find((a) => a.id === ACTIVE_ID)!;
      expect(row.router_hint).toBe("ภาษีทุกชนิด");
      expect(row.priority).toBe(5);
    });
  });

  it("edits data scope", async () => {
    const user = userEvent.setup();
    render(wrap(<RoutingTab agency={activeAgency()} />));
    await user.type(screen.getByPlaceholderText(/เพิ่มขอบเขตข้อมูล/), "ภาษีมูลค่าเพิ่ม");
    await user.click(screen.getByRole("button", { name: "เพิ่มขอบเขต" }));
    await user.click(screen.getByRole("button", { name: /บันทึก/ }));
    await waitFor(() =>
      expect(mockAgencies.find((a) => a.id === ACTIVE_ID)!.data_scope).toContain("ภาษีมูลค่าเพิ่ม"),
    );
  });

  it("shows wizard-style gray placeholders for empty routing fields", () => {
    render(wrap(<RoutingTab agency={activeAgency()} />));
    expect(screen.getByPlaceholderText(/อธิบายว่าหน่วยงานนี้ตอบคำถาม/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("เช่น 1")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("ค่าเริ่มต้นระบบ")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("ไม่จำกัด")).toBeInTheDocument();
  });
});
