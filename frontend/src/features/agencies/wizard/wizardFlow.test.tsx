import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { mockAgencies, resetMockData } from "@/mocks/fixtures";
import { server } from "@/mocks/server";

import AgencyWizardPage from "./AgencyWizardPage";

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => {
  server.resetHandlers();
  resetMockData();
});
afterAll(() => server.close());

function renderWizard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/agencies/new"]}>
        <Routes>
          <Route path="/agencies/new" element={<AgencyWizardPage />} />
          <Route path="/agencies/:id" element={<div>detail-page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("wizard full flow (API agency)", () => {
  it("creates an active agency through all five steps", async () => {
    const user = userEvent.setup();
    renderWizard();

    // Step 1 — general
    await user.type(screen.getByLabelText("ชื่อหน่วยงาน"), "กรมศุลกากร");
    await user.type(screen.getByLabelText("ชื่อย่อ"), "ศก.");
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));

    // Step 2 — connection (API default)
    await user.type(screen.getByLabelText("Endpoint URL"), "https://customs.example/api/chat");
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));

    // Draft was persisted on leaving step 2
    await waitFor(() => expect(mockAgencies.some((a) => a.name === "กรมศุลกากร")).toBe(true));
    const created = mockAgencies.find((a) => a.name === "กรมศุลกากร")!;
    expect(created.status).toBe("draft");

    // Step 3 — test (optional, skip)
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));

    // Step 4 — routing
    await user.type(screen.getByLabelText(/Router hint/), "คำถามภาษีนำเข้า");
    await user.type(screen.getByLabelText(/Priority/), "2");
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));

    // Step 5 — review shows entered data, then activate
    expect(screen.getByText("กรมศุลกากร")).toBeInTheDocument();
    expect(screen.getByText("https://customs.example/api/chat")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /เปิดใช้งาน/ }));

    await waitFor(() => expect(screen.getByText("detail-page")).toBeInTheDocument());
    const final = mockAgencies.find((a) => a.name === "กรมศุลกากร")!;
    expect(final.status).toBe("active");
    expect(final.router_hint).toBe("คำถามภาษีนำเข้า");
    expect(final.priority).toBe(2);
  });

  it("saves as draft from the review step", async () => {
    const user = userEvent.setup();
    renderWizard();

    await user.type(screen.getByLabelText("ชื่อหน่วยงาน"), "กรมป่าไม้");
    await user.type(screen.getByLabelText("ชื่อย่อ"), "ปม.");
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));
    await user.type(screen.getByLabelText("Endpoint URL"), "https://forest.example/api");
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));
    await user.click(screen.getByRole("button", { name: /ถัดไป/ }));
    await user.click(screen.getByRole("button", { name: /บันทึกเป็น Draft/ }));

    await waitFor(() => expect(screen.getByText("detail-page")).toBeInTheDocument());
    expect(mockAgencies.find((a) => a.name === "กรมป่าไม้")!.status).toBe("draft");
  });
});
