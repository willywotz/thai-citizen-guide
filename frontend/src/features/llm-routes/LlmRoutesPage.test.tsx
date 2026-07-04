import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LlmRoutesPage from "./LlmRoutesPage";
import type { LlmRoute } from "./llmRouteApi";
import type { LlmProvider } from "@/features/llm-providers/llmProviderApi";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const auth = { isReadOnly: false };
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));

const mockListRoutes = vi.fn();
const mockCreateRoute = vi.fn();
const mockUpdateRoute = vi.fn();
const mockDeleteRoute = vi.fn();
const mockListPurposes = vi.fn();

vi.mock("@/features/llm-routes/llmRouteApi", () => ({
  listRoutes: (...args: unknown[]) => mockListRoutes(...args),
  createRoute: (...args: unknown[]) => mockCreateRoute(...args),
  updateRoute: (...args: unknown[]) => mockUpdateRoute(...args),
  deleteRoute: (...args: unknown[]) => mockDeleteRoute(...args),
  listPurposes: (...args: unknown[]) => mockListPurposes(...args),
}));

const mockListProviders = vi.fn();

vi.mock("@/features/llm-providers/llmProviderApi", () => ({
  listProviders: (...args: unknown[]) => mockListProviders(...args),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeRoute = (overrides: Partial<LlmRoute> = {}): LlmRoute => ({
  id: "r1",
  purpose: "chat",
  provider_id: "p1",
  provider_name: "OpenAI",
  model: "gpt-4o",
  timeout_override: null,
  enabled: true,
  ...overrides,
});

const makeProvider = (overrides: Partial<LlmProvider> = {}): LlmProvider => ({
  id: "p1",
  name: "OpenAI",
  base_url: "https://api.openai.com/v1",
  api_key: "*****",
  auth_header: "Authorization",
  auth_scheme: "Bearer",
  timeout_seconds: 60,
  request_usage: false,
  rate_limit_rps: null,
  rate_limit_rpm: null,
  max_queue_size: 50,
  enabled: true,
  ...overrides,
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <LlmRoutesPage />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LlmRoutesPage create button", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
    mockListRoutes.mockResolvedValue({ data: [], total: 0 });
    mockListPurposes.mockResolvedValue({ data: ["chat", "classification"] });
    mockListProviders.mockResolvedValue({ data: [makeProvider()], total: 1 });
  });

  afterEach(() => vi.clearAllMocks());

  it("shows the create button for a writer", async () => {
    renderPage();
    expect(await screen.findByText("เพิ่มเส้นทาง")).toBeInTheDocument();
  });

  it("hides the create button for a read-only role", async () => {
    auth.isReadOnly = true;
    renderPage();
    await screen.findByText("ยังไม่มีเส้นทาง LLM กรุณาเพิ่มใหม่");
    expect(screen.queryByText("เพิ่มเส้นทาง")).not.toBeInTheDocument();
  });
});

describe("LlmRoutesPage list rendering", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
    mockListPurposes.mockResolvedValue({ data: ["chat", "classification"] });
    mockListProviders.mockResolvedValue({ data: [makeProvider()], total: 1 });
  });

  afterEach(() => vi.clearAllMocks());

  it("shows empty state when there are no routes", async () => {
    mockListRoutes.mockResolvedValue({ data: [], total: 0 });
    renderPage();
    expect(await screen.findByText("ยังไม่มีเส้นทาง LLM กรุณาเพิ่มใหม่")).toBeInTheDocument();
  });

  it("renders route cards with purpose, provider and model", async () => {
    mockListRoutes.mockResolvedValue({
      data: [
        makeRoute({ id: "r1", purpose: "chat" }),
        makeRoute({ id: "r2", purpose: "classification", enabled: false }),
      ],
      total: 2,
    });
    renderPage();
    expect(await screen.findByText("chat")).toBeInTheDocument();
    expect(screen.getByText("classification")).toBeInTheDocument();
    expect(screen.getAllByText(/OpenAI · gpt-4o/).length).toBeGreaterThan(0);
    expect(screen.getByText("ปิดใช้งาน")).toBeInTheDocument();
  });

  it("hides action buttons for read-only users", async () => {
    auth.isReadOnly = true;
    mockListRoutes.mockResolvedValue({ data: [makeRoute()], total: 1 });
    renderPage();
    await screen.findByText("chat");
    expect(screen.queryByRole("button", { name: "แก้ไข" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ลบ" })).not.toBeInTheDocument();
  });
});

describe("LlmRoutesPage create flow", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
    mockListRoutes.mockResolvedValue({ data: [], total: 0 });
    mockListPurposes.mockResolvedValue({ data: ["chat", "classification"] });
    mockListProviders.mockResolvedValue({ data: [makeProvider({ id: "p1", name: "OpenAI" })], total: 1 });
  });

  afterEach(() => vi.clearAllMocks());

  it("opens create dialog when button is clicked", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /เพิ่มเส้นทาง/ }));
    expect(screen.getByText("เพิ่มเส้นทาง LLM")).toBeInTheDocument();
    expect(screen.getByLabelText("วัตถุประสงค์ (Purpose)")).toBeInTheDocument();
  });

  it("submit button is disabled when required fields are empty", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /เพิ่มเส้นทาง/ }));
    expect(screen.getByRole("button", { name: /^สร้าง$/ })).toBeDisabled();
  });

  it("calls createRoute with form values on submit, coercing empty timeout to null", async () => {
    mockCreateRoute.mockResolvedValue(makeRoute({ id: "new-1" }));
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /เพิ่มเส้นทาง/ }));

    await userEvent.click(screen.getByLabelText("วัตถุประสงค์ (Purpose)"));
    await userEvent.click(await screen.findByRole("option", { name: "chat" }));

    await userEvent.click(screen.getByLabelText("ผู้ให้บริการ (Provider)"));
    await userEvent.click(await screen.findByRole("option", { name: "OpenAI" }));

    await userEvent.type(screen.getByLabelText("โมเดล (Model)"), "gpt-4o");
    await userEvent.click(screen.getByRole("button", { name: /^สร้าง$/ }));

    await waitFor(() =>
      expect(mockCreateRoute).toHaveBeenCalledWith({
        purpose: "chat",
        provider_id: "p1",
        model: "gpt-4o",
        timeout_override: null,
        enabled: true,
      }),
    );
    await waitFor(() => expect(screen.queryByText("เพิ่มเส้นทาง LLM")).not.toBeInTheDocument());
  });

  it("preserves an explicit 0 for timeout_override instead of coercing to null", async () => {
    mockCreateRoute.mockResolvedValue(makeRoute({ id: "new-2", timeout_override: 0 }));
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /เพิ่มเส้นทาง/ }));

    await userEvent.click(screen.getByLabelText("วัตถุประสงค์ (Purpose)"));
    await userEvent.click(await screen.findByRole("option", { name: "chat" }));

    await userEvent.click(screen.getByLabelText("ผู้ให้บริการ (Provider)"));
    await userEvent.click(await screen.findByRole("option", { name: "OpenAI" }));

    await userEvent.type(screen.getByLabelText("โมเดล (Model)"), "gpt-4o");

    const timeoutInput = screen.getByLabelText("หมดเวลาเฉพาะเส้นทาง (วินาที)");
    await userEvent.type(timeoutInput, "0");

    await userEvent.click(screen.getByRole("button", { name: /^สร้าง$/ }));

    await waitFor(() =>
      expect(mockCreateRoute).toHaveBeenCalledWith(
        expect.objectContaining({ timeout_override: 0 }),
      ),
    );
  });
});

describe("LlmRoutesPage edit flow", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
    mockListPurposes.mockResolvedValue({ data: ["chat", "classification"] });
    mockListProviders.mockResolvedValue({
      data: [
        makeProvider({ id: "p1", name: "OpenAI" }),
        makeProvider({ id: "p2", name: "Azure" }),
      ],
      total: 2,
    });
  });

  afterEach(() => vi.clearAllMocks());

  it("opens edit dialog with the purpose shown read-only", async () => {
    mockListRoutes.mockResolvedValue({ data: [makeRoute({ purpose: "chat" })], total: 1 });
    renderPage();

    await screen.findByText("chat");
    await userEvent.click(screen.getByRole("button", { name: "แก้ไข" }));

    expect(screen.getByText("แก้ไขเส้นทาง LLM")).toBeInTheDocument();
    const purposeField = screen.getByLabelText("วัตถุประสงค์ (Purpose)") as HTMLInputElement;
    expect(purposeField.value).toBe("chat");
    expect(purposeField).toBeDisabled();
  });

  it("omits purpose from the update payload and sends the new model/provider", async () => {
    const route = makeRoute({ id: "r1", purpose: "chat", provider_id: "p1", model: "gpt-4o" });
    mockListRoutes.mockResolvedValue({ data: [route], total: 1 });
    mockUpdateRoute.mockResolvedValue({ ...route, model: "gpt-4o-mini" });

    renderPage();

    await screen.findByText("chat");
    await userEvent.click(screen.getByRole("button", { name: "แก้ไข" }));

    const modelInput = screen.getByLabelText("โมเดล (Model)");
    await userEvent.clear(modelInput);
    await userEvent.type(modelInput, "gpt-4o-mini");

    await userEvent.click(screen.getByLabelText("ผู้ให้บริการ (Provider)"));
    await userEvent.click(await screen.findByRole("option", { name: "Azure" }));

    await userEvent.click(screen.getByRole("button", { name: /บันทึก/ }));

    await waitFor(() => expect(mockUpdateRoute).toHaveBeenCalled());
    const [id, body] = mockUpdateRoute.mock.calls[0];
    expect(id).toBe("r1");
    expect(body).not.toHaveProperty("purpose");
    expect(body.model).toBe("gpt-4o-mini");
    expect(body.provider_id).toBe("p2");
  });
});

describe("LlmRoutesPage delete flow", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
    mockListPurposes.mockResolvedValue({ data: ["chat", "classification"] });
    mockListProviders.mockResolvedValue({ data: [makeProvider()], total: 1 });
  });

  afterEach(() => vi.clearAllMocks());

  it("opens delete confirm dialog when delete button is clicked", async () => {
    mockListRoutes.mockResolvedValue({ data: [makeRoute({ purpose: "chat" })], total: 1 });
    renderPage();

    await screen.findByText("chat");
    await userEvent.click(screen.getByRole("button", { name: "ลบ" }));

    expect(screen.getByText("ยืนยันการลบ")).toBeInTheDocument();
    expect(screen.getByText(/ลบเส้นทาง "chat"/)).toBeInTheDocument();
  });

  it("calls deleteRoute with the correct id when confirm ลบ is clicked", async () => {
    mockListRoutes.mockResolvedValue({ data: [makeRoute({ id: "r1", purpose: "chat" })], total: 1 });
    mockDeleteRoute.mockResolvedValue(undefined);

    renderPage();

    await screen.findByText("chat");
    await userEvent.click(screen.getByRole("button", { name: "ลบ" }));
    await screen.findByText("ยืนยันการลบ");

    const allBtns = screen.getAllByRole("button");
    const confirmBtn = allBtns.find(
      (b) => b.textContent?.trim() === "ลบ" && !b.hasAttribute("aria-label"),
    );
    await userEvent.click(confirmBtn!);

    await waitFor(() => expect(mockDeleteRoute).toHaveBeenCalledWith("r1"));
    await waitFor(() => expect(screen.queryByText("ยืนยันการลบ")).not.toBeInTheDocument());
  });

  it("dismisses delete dialog on cancel", async () => {
    mockListRoutes.mockResolvedValue({ data: [makeRoute({ purpose: "chat" })], total: 1 });
    renderPage();

    await screen.findByText("chat");
    await userEvent.click(screen.getByRole("button", { name: "ลบ" }));
    await screen.findByText("ยืนยันการลบ");
    await userEvent.click(screen.getByRole("button", { name: "ยกเลิก" }));

    await waitFor(() => expect(screen.queryByText("ยืนยันการลบ")).not.toBeInTheDocument());
    expect(mockDeleteRoute).not.toHaveBeenCalled();
  });
});
