"use client";

import { useEffect, useState } from "react";
import { useFilters, filtersToQuery } from "./filters";
import type { ApiEnvelope, Filters } from "./types";

interface StatsState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

// Fetch một stats route, tự build query từ filter state chung + refetch khi filter đổi.
export function useStats<T>(
  route: string,
  extra?: Record<string, string | number>
): StatsState<T> {
  const { filters } = useFilters();
  const [state, setState] = useState<StatsState<T>>({ data: null, loading: true, error: null });
  const qs = filtersToQuery(filters, extra);

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    fetch(`${route}?${qs}`)
      .then(async (res) => {
        const json = (await res.json()) as ApiEnvelope<T>;
        if (cancelled) return;
        if (json.success) setState({ data: json.data ?? null, loading: false, error: null });
        else setState({ data: null, loading: false, error: json.message ?? "Lỗi" });
      })
      .catch((e) => {
        if (!cancelled) setState({ data: null, loading: false, error: String(e) });
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
