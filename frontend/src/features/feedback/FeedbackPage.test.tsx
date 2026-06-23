import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { ThemeProvider } from "next-themes";
import { describe, expect, it } from "vitest";

import FeedbackPage from "./FeedbackPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ThemeProvider attribute="class">
        <FeedbackPage />
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

describe("FeedbackPage", () => {
  it("renders summary cards, charts, and low-rated questions from stats", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Feedback ทั้งหมด")).toBeInTheDocument());
    expect(screen.getByText("แนวโน้มความพึงพอใจรายวัน (14 วัน)")).toBeInTheDocument();
    expect(screen.getByText("ความพึงพอใจแยกตามหน่วยงาน")).toBeInTheDocument();
    expect(screen.getByText("คำถามที่ได้คะแนนต่ำ (ล่าสุด)")).toBeInTheDocument();
    expect(screen.getByText("ทำไมระบบตอบช้า")).toBeInTheDocument();
  });
});
