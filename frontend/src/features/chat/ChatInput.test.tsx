import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChatInput } from "./ChatInput";

describe("ChatInput", () => {
  const baseProps = {
    input: "",
    setInput: vi.fn(),
    isTyping: false,
    onSend: vi.fn(),
    onCancel: vi.fn(),
  };

  it("disables the send button when the input is empty", () => {
    render(<ChatInput {...baseProps} input="" />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("sends on click when the input has text", async () => {
    const onSend = vi.fn();
    render(<ChatInput {...baseProps} input="hello" onSend={onSend} />);
    await userEvent.click(screen.getByRole("button"));
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("sends on Enter without shift", async () => {
    const onSend = vi.fn();
    render(<ChatInput {...baseProps} input="hi" onSend={onSend} />);
    await userEvent.type(screen.getByPlaceholderText(/พิมพ์คำถาม/), "{Enter}");
    expect(onSend).toHaveBeenCalled();
  });

  it("shows a cancel button while typing and calls onCancel", async () => {
    const onCancel = vi.fn();
    render(<ChatInput {...baseProps} isTyping onCancel={onCancel} />);
    await userEvent.click(screen.getByTitle("ยกเลิก"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
