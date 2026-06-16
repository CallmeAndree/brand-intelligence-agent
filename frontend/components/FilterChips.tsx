"use client";

import { useFilters, FilterDim } from "@/lib/filters";

const LABELS: Record<FilterDim, string> = {
  platform: "Nền tảng",
  severityBand: "Mức độ",
  productArea: "Sản phẩm",
  topic: "Chủ đề",
  clusterId: "Cụm chủ đề",
  keywordGroupId: "Cụm keyword",
  intent: "Ý định",
  actionableOnly: "Cần xử lý",
};

const DIMS: FilterDim[] = [
  "platform",
  "severityBand",
  "productArea",
  "topic",
  "clusterId",
  "keywordGroupId",
  "intent",
  "actionableOnly",
];

export default function FilterChips() {
  const { filters, clearDim, clearAll } = useFilters();
  const fmap = filters as unknown as Record<string, unknown>;
  const active = DIMS.filter((d) => fmap[d] != null);

  if (active.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {active.map((dim) => {
        const val = fmap[dim];
        const text =
          dim === "actionableOnly" ? LABELS[dim] : `${LABELS[dim]}: ${val}`;
        return (
          <span
            key={dim}
            className="inline-flex items-center gap-1.5 rounded-full bg-feature-cream px-3 py-1 text-caption"
          >
            {text}
            <button
              onClick={() => clearDim(dim)}
              className="text-ink/50 hover:text-error"
              aria-label={`Bỏ lọc ${LABELS[dim]}`}
            >
              ✕
            </button>
          </span>
        );
      })}
      <button
        onClick={clearAll}
        className="text-body-sm text-ink/60 underline hover:text-ink"
      >
        Xóa tất cả
      </button>
    </div>
  );
}
