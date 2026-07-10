import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { server } from "@/mocks/server";
import PublicPortal from "./PublicPortal";

vi.mock("@/features/chat/useChat", () => ({
  useChat: () => ({
    messages: [],
    input: "",
    setInput: vi.fn(),
    isTyping: false,
    activeStepCount: 0,
    currentSteps: [],
    streamingState: { pipelineSteps: [], done: false },
    scrollRef: { current: null },
    handleSend: vi.fn(),
    handleRate: vi.fn(),
    reset: vi.fn(),
    cancelStream: vi.fn(),
    hasMessages: false,
  }),
}));

function renderPortal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <PublicPortal />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => server.resetHandlers());

describe("PublicPortal popular questions", () => {
  it("renders fetched popular questions", async () => {
    renderPortal();
    expect(await screen.findByText("คำถามยอดนิยม")).toBeInTheDocument();
    expect(await screen.findByText("สอบถามเรื่องการลดหย่อนภาษี 2568")).toBeInTheDocument();
  });

  it("renders nothing when the endpoint returns an empty list", async () => {
    server.use(
      http.get("*/api/v1/public/popular-questions", () => HttpResponse.json({ questions: [] })),
    );
    renderPortal();
    await waitFor(() => expect(screen.queryByText("คำถามยอดนิยม")).not.toBeInTheDocument());
  });
});
