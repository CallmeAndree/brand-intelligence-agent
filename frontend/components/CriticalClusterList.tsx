"use client";

import { Card, Loading, ErrorBox, EmptyState } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { usePinnedClusters } from "@/lib/pins";
import { bandOf, bandColor } from "@/lib/severity";
import type { CriticalCluster, Trend } from "@/lib/types";

const TREND_ICON: Record<Trend, string> = { up: "↑", down: "↓", flat: "→" };
const TREND_CLASS: Record<Trend, string> = {
  up: "text-error",
  down: "text-feature-teal",
  flat: "text-ink/40",
};

// Icon ghim (lucide "pin"), tô currentColor → đổi màu theo trạng thái ghim.
function PinIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M12 17v5" />
      <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z" />
    </svg>
  );
}

export default function CriticalClusterList() {
  const { filters, setDim } = useFilters();
  const { isPinned, toggle } = usePinnedClusters();
  const { data, loading, error } = useStats<CriticalCluster[]>(
    "/api/clusters/critical",
  );
  const selected = filters.clusterId;

  // Cụm đã ghim nổi lên đầu (sort ỔN ĐỊNH → giữ thứ tự gốc trong từng nhóm).
  const ordered = data
    ? [...data].sort(
        (a, b) =>
          Number(isPinned(b.cluster_id)) - Number(isPinned(a.cluster_id)),
      )
    : [];

  return (
    <Card
      title="Các chủ đề nổi bật"
      subtitle="Ghim 📌 chủ đề muốn theo dõi để giữ nó luôn trên đầu."
      scroll
      className="h-full"
    >
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorBox message={error} />
      ) : !data || data.length === 0 ? (
        <EmptyState message="Không có chủ đề nổi bật nào trong khoảng ngày này" />
      ) : (
        <ul className="space-y-2">
          {ordered.map((c) => {
            const band = bandOf(c.severity_max);
            const isSel = selected === String(c.cluster_id);
            const pinned = isPinned(c.cluster_id);
            return (
              <li key={c.cluster_id} className="relative">
                <button
                  onClick={() => setDim("clusterId", String(c.cluster_id))}
                  className={`w-full rounded-[12px] border p-3 text-left transition ${
                    isSel
                      ? "border-feature-blue bg-feature-blue/10"
                      : pinned
                        ? "border-feature-peach bg-feature-peach/15 hover:bg-feature-peach/25"
                        : "border-ink/10 bg-white/50 hover:bg-feature-cream/50"
                  }`}
                >
                  {/* pr-7: chừa chỗ cho nút ghim ở góc trên-phải, tránh đè nhãn/badge */}
                  <div className="flex items-start justify-between gap-2 pr-7">
                    <span className="line-clamp-2 text-body-sm font-medium text-ink/90">
                      {c.label}
                    </span>
                    <span
                      className="shrink-0 rounded px-1.5 py-0.5 text-caption font-semibold text-white"
                      style={{ backgroundColor: band ? bandColor(band) : "#c9c2b0" }}
                    >
                      {c.severity_max}
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-3 text-caption text-ink/60">
                    <span>{c.count.toLocaleString("vi-VN")} mention</span>
                    <span className={TREND_CLASS[c.trend]}>
                      {TREND_ICON[c.trend]} {c.trend}
                    </span>
                  </div>
                </button>
                {/* Nút ghim tách riêng (absolute) → không lồng trong button chọn cụm. */}
                <button
                  type="button"
                  onClick={() => toggle(c.cluster_id)}
                  aria-pressed={pinned}
                  aria-label={pinned ? "Bỏ ghim chủ đề" : "Ghim chủ đề để theo dõi"}
                  title={pinned ? "Bỏ ghim" : "Ghim để theo dõi"}
                  className={`absolute right-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-full transition ${
                    pinned
                      ? "text-feature-peach hover:bg-feature-peach/20"
                      : "text-ink/25 hover:bg-ink/5 hover:text-ink/60"
                  }`}
                >
                  <PinIcon filled={pinned} />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
