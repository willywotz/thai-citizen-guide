import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";

import { resetMockData } from "@/mocks/fixtures";
import { server } from "@/mocks/server";

import { StepTest } from "./StepTest";

afterEach(() => {
  resetMockData();
});

const ACTIVE_ID = "11111111-1111-1111-1111-111111111111";

function wrap(children: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("StepTest", () => {
  it("runs the connection test and shows the result", async () => {
    render(wrap(<StepTest agencyId={ACTIVE_ID} />));
    await userEvent.click(screen.getByRole("button", { name: /ทดสอบการเชื่อมต่อ/ }));
    await waitFor(() => expect(screen.getByText(/Handshake/)).toBeInTheDocument());
  });

  it("shows a non-blocking failure message on error", async () => {
    server.use(
      http.get("*/api/v1/agencies/:id/test", () =>
        HttpResponse.json({ detail: "boom" }, { status: 502 }),
      ),
    );
    render(wrap(<StepTest agencyId={ACTIVE_ID} />));
    await userEvent.click(screen.getByRole("button", { name: /ทดสอบการเชื่อมต่อ/ }));
    await waitFor(() => expect(screen.getByText(/ทดสอบไม่สำเร็จ/)).toBeInTheDocument());
  });
});
