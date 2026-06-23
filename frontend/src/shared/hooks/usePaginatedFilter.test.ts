import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { usePaginatedFilter } from "./usePaginatedFilter";

const items = Array.from({ length: 25 }, (_, i) => ({ id: i + 1, name: `item-${i + 1}` }));

describe("usePaginatedFilter", () => {
  it("returns first page slice with default page 1", () => {
    const { result } = renderHook(() =>
      usePaginatedFilter({ items, pageSize: 10 }),
    );
    expect(result.current.pageItems).toHaveLength(10);
    expect(result.current.pageItems[0]).toEqual({ id: 1, name: "item-1" });
    expect(result.current.pageItems[9]).toEqual({ id: 10, name: "item-10" });
  });

  it("returns correct total and totalPages", () => {
    const { result } = renderHook(() =>
      usePaginatedFilter({ items, pageSize: 10 }),
    );
    expect(result.current.total).toBe(25);
    expect(result.current.totalPages).toBe(3);
  });

  it("returns last page (partial) correctly", () => {
    const { result } = renderHook(() =>
      usePaginatedFilter({ items, pageSize: 10 }),
    );
    act(() => result.current.setPage(3));
    expect(result.current.pageItems).toHaveLength(5);
    expect(result.current.pageItems[0]).toEqual({ id: 21, name: "item-21" });
  });

  it("clamps page to totalPages when items shrink", () => {
    const { result, rerender } = renderHook(
      ({ data }: { data: typeof items }) => usePaginatedFilter({ items: data, pageSize: 10 }),
      { initialProps: { data: items } },
    );
    act(() => result.current.setPage(3));
    expect(result.current.page).toBe(3);

    // Shrink to 5 items — page 3 is out of range
    rerender({ data: items.slice(0, 5) });
    expect(result.current.page).toBe(1);
    expect(result.current.pageItems).toHaveLength(5);
  });

  it("applies filterFn and returns filtered total", () => {
    const { result } = renderHook(() =>
      usePaginatedFilter({
        items,
        pageSize: 10,
        filterFn: (item) => item.id % 2 === 0,
      }),
    );
    expect(result.current.total).toBe(12);
    expect(result.current.totalPages).toBe(2);
    expect(result.current.pageItems[0]).toEqual({ id: 2, name: "item-2" });
  });

  it("resets to page 1 when filterFn identity changes", () => {
    const { result, rerender } = renderHook(
      ({ filterFn }: { filterFn: (item: { id: number; name: string }) => boolean }) =>
        usePaginatedFilter({ items, pageSize: 10, filterFn }),
      { initialProps: { filterFn: () => true } },
    );
    act(() => result.current.setPage(2));
    expect(result.current.page).toBe(2);

    // Change filter — should reset page
    rerender({ filterFn: (item) => item.id <= 5 });
    expect(result.current.page).toBe(1);
    expect(result.current.total).toBe(5);
  });

  it("returns totalPages of at least 1 for empty list", () => {
    const { result } = renderHook(() =>
      usePaginatedFilter({ items: [], pageSize: 10 }),
    );
    expect(result.current.totalPages).toBe(1);
    expect(result.current.pageItems).toHaveLength(0);
    expect(result.current.total).toBe(0);
  });

  it("provides correct page value via result", () => {
    const { result } = renderHook(() =>
      usePaginatedFilter({ items, pageSize: 10 }),
    );
    expect(result.current.page).toBe(1);
    act(() => result.current.setPage(2));
    expect(result.current.page).toBe(2);
  });

  it("exposes page state so pages can sync UI", () => {
    const { result } = renderHook(() =>
      usePaginatedFilter({ items, pageSize: 10 }),
    );
    act(() => result.current.setPage(2));
    expect(result.current.pageItems[0]).toEqual({ id: 11, name: "item-11" });
  });

  it("resets to page 1 when resetKey changes", () => {
    const { result, rerender } = renderHook(
      ({ resetKey }: { resetKey: string }) =>
        usePaginatedFilter({ items, pageSize: 10, resetKey }),
      { initialProps: { resetKey: "a" } },
    );
    act(() => result.current.setPage(2));
    expect(result.current.page).toBe(2);

    rerender({ resetKey: "b" });
    expect(result.current.page).toBe(1);
  });

  it("exposes filteredItems as the full filtered list (not sliced)", () => {
    const { result } = renderHook(() =>
      usePaginatedFilter({
        items,
        pageSize: 10,
        filterFn: (item) => item.id <= 15,
      }),
    );
    expect(result.current.filteredItems).toHaveLength(15);
    expect(result.current.pageItems).toHaveLength(10);
  });
});
