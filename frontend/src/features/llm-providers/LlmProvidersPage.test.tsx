import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LlmProvidersPage from "./LlmProvidersPage";
import type { LlmProvider } from "./llmProviderApi";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const auth = { isReadOnly: false };
vi.mock("@/features/auth/useAuth", () => ({ useAuth: () => auth }));

const mockListProviders = vi.fn();
const mockCreateProvider = vi.fn();
const mockUpdateProvider = vi.fn();
const mockDeleteProvider = vi.fn();

vi.mock("@/features/llm-providers/llmProviderApi", () => ({
  listProviders: (...args: unknown[]) => mockListProviders(...args),
  createProvider: (...args: unknown[]) => mockCreateProvider(...args),
  updateProvider: (...args: unknown[]) => mockUpdateProvider(...args),
  deleteProvider: (...args: unknown[]) => mockDeleteProvider(...args),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

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
      <LlmProvidersPage />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LlmProvidersPage create button", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
    mockListProviders.mockResolvedValue({ data: [], total: 0 });
  });

  afterEach(() => vi.clearAllMocks());

  it("shows the create button for a writer", async () => {
    renderPage();
    expect(await screen.findByText("เพิ่มผู้ให้บริการ")).toBeInTheDocument();
  });

  it("hides the create button for a read-only role", async () => {
    auth.isReadOnly = true;
    renderPage();
    await screen.findByText("ยังไม่มีผู้ให้บริการ LLM กรุณาเพิ่มใหม่");
    expect(screen.queryByText("เพิ่มผู้ให้บริการ")).not.toBeInTheDocument();
  });
});

describe("LlmProvidersPage list rendering", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
  });

  afterEach(() => vi.clearAllMocks());

  it("shows empty state when there are no providers", async () => {
    mockListProviders.mockResolvedValue({ data: [], total: 0 });
    renderPage();
    expect(await screen.findByText("ยังไม่มีผู้ให้บริการ LLM กรุณาเพิ่มใหม่")).toBeInTheDocument();
  });

  it("renders provider cards with name and base_url", async () => {
    mockListProviders.mockResolvedValue({
      data: [
        makeProvider({ id: "p1", name: "OpenAI" }),
        makeProvider({ id: "p2", name: "Azure", enabled: false }),
      ],
      total: 2,
    });
    renderPage();
    expect(await screen.findByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Azure")).toBeInTheDocument();
    expect(screen.getByText("ปิดใช้งาน")).toBeInTheDocument();
  });

  it("hides action buttons for read-only users", async () => {
    auth.isReadOnly = true;
    mockListProviders.mockResolvedValue({ data: [makeProvider()], total: 1 });
    renderPage();
    await screen.findByText("OpenAI");
    expect(screen.queryByRole("button", { name: "แก้ไข" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "ลบ" })).not.toBeInTheDocument();
  });
});

describe("LlmProvidersPage create flow", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
    mockListProviders.mockResolvedValue({ data: [], total: 0 });
  });

  afterEach(() => vi.clearAllMocks());

  it("opens create dialog when button is clicked", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /เพิ่มผู้ให้บริการ/ }));
    expect(screen.getByText("เพิ่มผู้ให้บริการ LLM")).toBeInTheDocument();
    expect(screen.getByLabelText("ชื่อ")).toBeInTheDocument();
  });

  it("submit button is disabled when required fields are empty", async () => {
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /เพิ่มผู้ให้บริการ/ }));
    expect(screen.getByRole("button", { name: /^สร้าง$/ })).toBeDisabled();
  });

  it("calls createProvider with form values on submit", async () => {
    mockCreateProvider.mockResolvedValue(makeProvider({ id: "new-1", name: "My Provider" }));
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /เพิ่มผู้ให้บริการ/ }));
    await userEvent.type(screen.getByLabelText("ชื่อ"), "My Provider");
    await userEvent.type(screen.getByLabelText("Base URL"), "https://my.example.com/v1");
    await userEvent.type(screen.getByLabelText("API Key"), "sk-secret");
    await userEvent.click(screen.getByRole("button", { name: /^สร้าง$/ }));

    await waitFor(() =>
      expect(mockCreateProvider).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "My Provider",
          base_url: "https://my.example.com/v1",
          api_key: "sk-secret",
          auth_header: "Authorization",
          auth_scheme: "Bearer",
          timeout_seconds: 60,
          request_usage: false,
          rate_limit_rps: null,
          rate_limit_rpm: null,
          max_queue_size: 50,
          enabled: true,
        }),
      ),
    );
    await waitFor(() => expect(screen.queryByText("เพิ่มผู้ให้บริการ LLM")).not.toBeInTheDocument());
  });
});

describe("LlmProvidersPage edit flow", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
  });

  afterEach(() => vi.clearAllMocks());

  it("opens edit dialog with pre-filled fields and a blank api_key", async () => {
    mockListProviders.mockResolvedValue({ data: [makeProvider({ name: "Original Name" })], total: 1 });
    renderPage();

    await screen.findByText("Original Name");
    await userEvent.click(screen.getByRole("button", { name: "แก้ไข" }));

    expect(screen.getByText("แก้ไขผู้ให้บริการ LLM")).toBeInTheDocument();
    expect((screen.getByLabelText("ชื่อ") as HTMLInputElement).value).toBe("Original Name");
    expect((screen.getByLabelText("API Key") as HTMLInputElement).value).toBe("");
  });

  it("omits api_key from the update payload when left blank", async () => {
    const provider = makeProvider({ id: "p1", name: "Old Name" });
    mockListProviders.mockResolvedValue({ data: [provider], total: 1 });
    mockUpdateProvider.mockResolvedValue({ ...provider, name: "New Name" });

    renderPage();

    await screen.findByText("Old Name");
    await userEvent.click(screen.getByRole("button", { name: "แก้ไข" }));

    const nameInput = screen.getByLabelText("ชื่อ");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "New Name");
    await userEvent.click(screen.getByRole("button", { name: /บันทึก/ }));

    await waitFor(() => expect(mockUpdateProvider).toHaveBeenCalled());
    const [id, body] = mockUpdateProvider.mock.calls[0];
    expect(id).toBe("p1");
    expect(body).not.toHaveProperty("api_key");
    expect(body.name).toBe("New Name");
  });

  it("includes api_key in the update payload when changed", async () => {
    const provider = makeProvider({ id: "p1", name: "Old Name" });
    mockListProviders.mockResolvedValue({ data: [provider], total: 1 });
    mockUpdateProvider.mockResolvedValue(provider);

    renderPage();

    await screen.findByText("Old Name");
    await userEvent.click(screen.getByRole("button", { name: "แก้ไข" }));
    await userEvent.type(screen.getByLabelText("API Key"), "sk-new-secret");
    await userEvent.click(screen.getByRole("button", { name: /บันทึก/ }));

    await waitFor(() => expect(mockUpdateProvider).toHaveBeenCalled());
    const [, body] = mockUpdateProvider.mock.calls[0];
    expect(body.api_key).toBe("sk-new-secret");
  });
});

describe("LlmProvidersPage delete flow", () => {
  beforeEach(() => {
    auth.isReadOnly = false;
  });

  afterEach(() => vi.clearAllMocks());

  it("opens delete confirm dialog when delete button is clicked", async () => {
    mockListProviders.mockResolvedValue({ data: [makeProvider({ name: "Provider To Delete" })], total: 1 });
    renderPage();

    await screen.findByText("Provider To Delete");
    await userEvent.click(screen.getByRole("button", { name: "ลบ" }));

    expect(screen.getByText("ยืนยันการลบ")).toBeInTheDocument();
    expect(screen.getByText(/ลบผู้ให้บริการ "Provider To Delete"/)).toBeInTheDocument();
  });

  it("calls deleteProvider with the correct id when confirm ลบ is clicked", async () => {
    mockListProviders.mockResolvedValue({ data: [makeProvider({ id: "p1", name: "Provider To Delete" })], total: 1 });
    mockDeleteProvider.mockResolvedValue(undefined);

    renderPage();

    await screen.findByText("Provider To Delete");
    await userEvent.click(screen.getByRole("button", { name: "ลบ" }));
    await screen.findByText("ยืนยันการลบ");

    const allBtns = screen.getAllByRole("button");
    const confirmBtn = allBtns.find(
      (b) => b.textContent?.trim() === "ลบ" && !b.hasAttribute("aria-label"),
    );
    await userEvent.click(confirmBtn!);

    await waitFor(() => expect(mockDeleteProvider).toHaveBeenCalledWith("p1"));
    await waitFor(() => expect(screen.queryByText("ยืนยันการลบ")).not.toBeInTheDocument());
  });

  it("dismisses delete dialog on cancel", async () => {
    mockListProviders.mockResolvedValue({ data: [makeProvider({ name: "Provider To Delete" })], total: 1 });
    renderPage();

    await screen.findByText("Provider To Delete");
    await userEvent.click(screen.getByRole("button", { name: "ลบ" }));
    await screen.findByText("ยืนยันการลบ");
    await userEvent.click(screen.getByRole("button", { name: "ยกเลิก" }));

    await waitFor(() => expect(screen.queryByText("ยืนยันการลบ")).not.toBeInTheDocument());
    expect(mockDeleteProvider).not.toHaveBeenCalled();
  });
});
