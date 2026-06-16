"use client";

import { useEffect, useState } from "react";
import { useFilters, filtersToQuery } from "./filters";
import type { ApiEnvelope, Filters } from "./types";

interface StatsState<T> {
  data: T | null;
  loading: boolean; // chỉ true khi chưa từng có data (first load)
  validating: boolean; // re-fetch trong khi đã có data (stale-while-revalidate)
  error: string | null;
}

// Fetch một stats route, tự build query từ filter state chung + refetch khi filter đổi.
// Stale-while-revalidate: đổi filter khi đã có data → giữ data cũ + validating; chỉ blank lần đầu.
export function useStats<T>(
  route: string,
  extra?: Record<string, string | number>
): StatsState<T> {
  const { filters } = useFilters();
  const [state, setState] = useState<StatsState<T>>({
    data: null,
    loading: true,
    validating: false,
    error: null,
  });
  const qs = filtersToQuery(filters, extra);

  useEffect(() => {
    let cancelled = false;
    // Có data → chỉ validating (giữ data hiển thị); chưa có → loading lần đầu.
    setState((s) =>
      s.data != null
        ? { ...s, validating: true, error: null }
        : { ...s, loading: true, validating: false, error: null }
    );
    fetch(`${route}?${qs}`)
      .then(async (res) => {
        const json = (await res.json()) as ApiEnvelope<T>;
        if (cancelled) return;
        if (json.success)
          setState({ data: json.data ?? null, loading: false, validating: false, error: null });
        // Lỗi logic: giữ data cũ, chỉ gắn error (StatefulChart chỉ hiện ErrorBox khi !data).
        else
          setState((s) => ({
            ...s,
            loading: false,
            validating: false,
            error: json.message ?? "Lỗi",
          }));
      })
      .catch((e) => {
        if (!cancelled)
          setState((s) => ({ ...s, loading: false, validating: false, error: String(e) }));
      });
    return () => {
      cancelled = true;
    };
  }, [route, qs]);

  return state;
}

// Helper rút filters ngoài hook (nếu cần build link).
export function buildQuery(filters: Filters, extra?: Record<string, string | number>): string {
  return filtersToQuery(filters, extra);
}
