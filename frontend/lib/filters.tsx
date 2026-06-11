"use client";

import React, { createContext, useContext, useMemo, useState, useCallback } from "react";
import type { Filters } from "./types";

const DEFAULT_FROM = process.env.NEXT_PUBLIC_DEFAULT_FROM || "2023-06-01";
const DEFAULT_TO = process.env.NEXT_PUBLIC_DEFAULT_TO || "2026-06-30";

export const DEFAULT_FILTERS: Filters = { from: DEFAULT_FROM, to: DEFAULT_TO };

// Các chiều cross-filter (không gồm dateRange — date có control riêng).
export type FilterDim = "platform" | "severityBand" | "productArea" | "topic" | "intent" | "actionableOnly";

interface FilterCtx {
  filters: Filters;
  setDim: (dim: FilterDim, value: Filters[FilterDim] | undefined) => void;
  setDateRange: (from: string, to: string) => void;
  clearDim: (dim: FilterDim) => void;
  clearAll: () => void;
}

const Ctx = createContext<FilterCtx | null>(null);

export function FilterProvider({ children }: { children: React.ReactNode }) {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);

  const setDim = useCallback((dim: FilterDim, value: Filters[FilterDim] | undefined) => {
    setFilters((prev) => {
      const next = { ...prev } as unknown as Record<string, unknown>;
      if (value === undefined || value === "" || value === false) {
        delete next[dim];
      } else {
        next[dim] = value;
      }
      return next as unknown as Filters;
    });
  }, []);

  const setDateRange = useCallback((from: string, to: string) => {
    setFilters((prev) => ({ ...prev, from, to }));
  }, []);

  const clearDim = useCallback((dim: FilterDim) => {
    setFilters((prev) => {
      const next = { ...prev } as unknown as Record<string, unknown>;
      delete next[dim];
      return next as unknown as Filters;
    });
  }, []);

  const clearAll = useCallback(() => setFilters(DEFAULT_FILTERS), []);

  const value = useMemo(
    () => ({ filters, setDim, setDateRange, clearDim, clearAll }),
    [filters, setDim, setDateRange, clearDim, clearAll]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFilters() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFilters must be used within FilterProvider");
  return ctx;
}

// Build query string từ filters (đẩy mọi chiều xuống API route).
export function filtersToQuery(filters: Filters, extra?: Record<string, string | number>): string {
  const sp = new URLSearchParams();
  sp.set("from", filters.from);
  sp.set("to", filters.to);
  if (filters.platform) sp.set("platform", filters.platform);
  if (filters.severityBand) sp.set("severityBand", filters.severityBand);
  if (filters.productArea) sp.set("productArea", filters.productArea);
  if (filters.topic) sp.set("topic", filters.topic);
  if (filters.intent) sp.set("intent", filters.intent);
  if (filters.actionableOnly) sp.set("actionable", "true");
  if (extra) for (const [k, v] of Object.entries(extra)) sp.set(k, String(v));
  return sp.toString();
}
