import { useEffect, useMemo, useState } from "react";

interface Options<T> {
  items: T[];
  pageSize: number;
  filterFn?: (item: T) => boolean;
  /** Changing this value resets the page to 1 — useful for server-side filters. */
  resetKey?: unknown;
}

interface Result<T> {
  pageItems: T[];
  filteredItems: T[];
  total: number;
  totalPages: number;
  page: number;
  setPage: (page: number) => void;
}

export function usePaginatedFilter<T>({ items, pageSize, filterFn, resetKey }: Options<T>): Result<T> {
  const [page, setPage] = useState(1);

  const filtered = useMemo(
    () => (filterFn ? items.filter(filterFn) : items),
    [items, filterFn],
  );

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));

  // Reset to page 1 when filterFn identity or resetKey changes
  useEffect(() => {
    setPage(1);
  }, [filterFn, resetKey]);

  const safePage = Math.min(page, totalPages);

  const pageItems = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, safePage, pageSize]);

  return {
    pageItems,
    filteredItems: filtered,
    total: filtered.length,
    totalPages,
    page: safePage,
    setPage,
  };
}
