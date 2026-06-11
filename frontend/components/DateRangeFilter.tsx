"use client";

import { useFilters, DEFAULT_FILTERS } from "@/lib/filters";

export default function DateRangeFilter() {
  const { filters, setDateRange } = useFilters();
  const isFull = filters.from === DEFAULT_FILTERS.from && filters.to === DEFAULT_FILTERS.to;

  return (
    <div className="flex items-center gap-2 text-sm">
      <input
        type="date"
        value={filters.from}
        onChange={(e) => setDateRange(e.target.value, filters.to)}
        className="rounded-[12px] border border-ink/15 bg-white px-3 py-2"
      />
      <span className="text-ink/50">→</span>
      <input
        type="date"
        value={filters.to}
        onChange={(e) => setDateRange(filters.from, e.target.value)}
        className="rounded-[12px] border border-ink/15 bg-white px-3 py-2"
      />
      {!isFull && (
        <button
          onClick={() => setDateRange(DEFAULT_FILTERS.from, DEFAULT_FILTERS.to)}
          className="rounded-[12px] border border-ink/15 bg-white px-3 py-2 hover:bg-feature-cream"
        >
          Toàn bộ
        </button>
      )}
    </div>
  );
}
