"use client";

import { Card, Loading, ErrorBox, EmptyState } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { bandOf, bandColor } from "@/lib/severity";
import type { CriticalCluster, Trend } from "@/lib/types";

const TREND_ICON: Record<Trend, string> = { up: "↑", down: "↓", flat: "→" };
const TREND_CLASS: Record<Trend, string> = {
  up: "text-error",
  down: "text-feature-teal",
  flat: "text-ink/40",
};

export default function CriticalClusterList() {
  const { filters, setDim } = useFilters();
  const { data, loading, error } = useStats<CriticalCluster[]>(
    "/api/clusters/critical",
  );
  const selected = filters.clusterId;

  return (
    <Card title="Cụm critical">
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox message={error} />
      ) : !data || data.length === 0 ? (
        <EmptyState message="Không có cụm nào vượt ngưỡng trong khoảng ngày này" />
      ) : (
        <ul className="space-y-2">
          {data.map((c) => {
            const band = bandOf(c.severity_max);
            const isSel = selected === String(c.cluster_id);
            return (
              <li key={c.cluster_id}>
                <button
                  onClick={() => setDim("clusterId", String(c.cluster_id))}
                  className={`w-full rounded-[12px] border p-3 text-left transition ${
                    isSel
                      ? "border-feature-pink bg-feature-pink/10"
                      : "border-ink/10 bg-white/50 hover:bg-feature-cream/50"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="line-clamp-2 text-sm font-medium text-ink/90">
                      {c.label}
                    </span>
                    <span
                      className="shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold text-white"
                      style={{ backgroundColor: band ? bandColor(band) : "#c9c2b0" }}
                    >
                      {c.severity_max}
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-3 text-xs text-ink/60">
                    <span>{c.count.toLocaleString("vi-VN")} mention</span>
                    <span className={TREND_CLASS[c.trend]}>
                      {TREND_ICON[c.trend]} {c.trend}
                    </span>
                    {c.last_seen && <span>· {c.last_seen.slice(0, 10)}</span>}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
