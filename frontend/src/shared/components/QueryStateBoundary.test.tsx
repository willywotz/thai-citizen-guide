import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryStateBoundary } from "./QueryStateBoundary";

describe("QueryStateBoundary", () => {
  it("renders children when data is available", () => {
    render(
      <QueryStateBoundary isLoading={false} isError={false} hasData onRetry={vi.fn()}>
        <span>content</span>
      </QueryStateBoundary>,
    );
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("renders loading skeleton when isLoading is true", () => {
    render(
      <QueryStateBoundary isLoading isError={false} hasData={false} onRetry={vi.fn()}>
        <span>content</span>
      </QueryStateBoundary>,
    );
    expect(screen.queryByText("content")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /ลองอีกครั้ง/ })).not.toBeInTheDocument();
  });

  it("shows retry on error and calls onRetry", () => {
    const onRetry = vi.fn();
    render(
      <QueryStateBoundary isLoading={false} isError hasData={false} onRetry={onRetry}>
        x
      </QueryStateBoundary>,
    );
    fireEvent.click(screen.getByRole("button", { name: /ลองอีกครั้ง/ }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("shows error UI with AlertCircle icon when isError is true", () => {
    render(
      <QueryStateBoundary isLoading={false} isError hasData={false} onRetry={vi.fn()}>
        x
      </QueryStateBoundary>,
    );
    expect(screen.queryByText("x")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ลองอีกครั้ง/ })).toBeInTheDocument();
  });
});
