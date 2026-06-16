"use client";

import { useEffect, useState } from "react";
import { bandOf, bandColor } from "@/lib/severity";
import type { ApiEnvelope, ClusterDetail } from "@/lib/types";

// Ngữ cảnh đang hoạt động của phiên chat: cụm (Monitor/cảnh báo) HOẶC data point dashboard.
export interface ActiveChatContext {
  source: "monitor" | "alert" | "dashboard";
  clusterId?: number; // nhánh cluster (monitor/alert)
  department?: string;
  preview?: string; // trích ngắn từ content_md / brief_md đã nạp
  // Nhánh dashboard-explain: chiều + nhãn + giá trị + số liệu quan sát của data point.
  dimension?: "month" | "platform" | "product_area" | "topic" | "keyword" | "risk";
  label?: string;
  value?: string;
  metric?: { name: string; value: number };
  // Chiều risk: data point 2 số → pill thứ hai (cạnh metric).
  metric2?: { name: string; value: number };
}

const DIMENSION_LABEL: Record<string, string> = {
  month: "Theo tháng",
  platform: "Nền tảng",
  product_area: "Mảng sản phẩm",
  topic: "Chủ đề",
  keyword: "Từ khóa",
  risk: "Ưu tiên xử lý",
};

interface Props {
  context: ActiveChatContext | null;
  onClear: () => void;
}

// Banner ngữ cảnh CỐ ĐỊNH phía trên khung chat — cho người dùng biết đang phân tích
// cụm nào (giống giao diện "chat về sản phẩm"). Tự nạp label/count/severity của cụm
// từ /api/clusters/{id}. Bám design/DESIGN.md: surface cream/feature, hairline, pill,
// token typography (label/title-sm/caption/body-sm). Không shadow nặng.
export default function ChatContextBanner({ context, onClear }: Props) {
  const [detail, setDetail] = useState<ClusterDetail | null>(null);

  useEffect(() => {
    setDetail(null);
    if (!context || context.source === "dashboard" || context.clusterId == null) return;
    let alive = true;
    fetch(`/api/clusters/${context.clusterId}?limit=1`)
      .then((r) => r.json() as Promise<ApiEnvelope<ClusterDetail>>)
      .then((d) => {
        if (alive && d.success && d.data) setDetail(d.data);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [context]);

  if (!context) return null;

  // Nhánh dashboard-explain: accent lavender (AI-agent), bám khuôn banner hiện có (D9/6.4).
  if (context.source === "dashboard") {
    return (
      <div className="mb-2 flex items-center gap-2 rounded-card border border-feature-lavender/40 bg-feature-lavender/15 px-3 py-1.5">
        <span className="shrink-0 text-sm" aria-hidden>
          ✨
        </span>
        <span className="hidden shrink-0 rounded-full bg-feature-lavender/30 px-2 py-0.5 text-label uppercase text-ink/55 sm:inline">
          {DIMENSION_LABEL[context.dimension ?? ""] ?? "Giải thích"}
        </span>
        <span className="min-w-0 flex-1 truncate text-body-sm font-semibold text-ink">
          {context.label ?? context.value}
        </span>
        {context.metric && (
          <span className="shrink-0 rounded-full border border-feature-lavender bg-feature-lavender/25 px-2 py-0.5 text-caption font-medium text-ink">
            {context.metric.name}: {context.metric.value}
          </span>
        )}
        {context.metric2 && (
          <span className="shrink-0 rounded-full border border-feature-lavender bg-feature-lavender/25 px-2 py-0.5 text-caption font-medium text-ink">
            {context.metric2.name}: {context.metric2.value}
          </span>
        )}
        <button
          type="button"
          onClick={onClear}
          aria-label="Bỏ ngữ cảnh"
          title="Bỏ ngữ cảnh"
          className="-mr-1 shrink-0 rounded-full px-1.5 py-0.5 text-lg leading-none text-ink/35 transition hover:bg-ink/5 hover:text-ink"
        >
          ×
        </button>
      </div>
    );
  }

  const isAlert = context.source === "alert";
  const label =
    detail?.label && detail.label !== `Cụm #${context.clusterId}` ? detail.label : null;
  const sevMax = detail?.severity_max ?? null;
  const band = bandOf(sevMax);

  return (
    <div
      className={`mb-2 flex items-center gap-2 rounded-card border px-3 py-1.5 ${
        isAlert
          ? "border-feature-blue/40 bg-feature-blue/10"
          : "border-feature-peach/50 bg-feature-peach/15"
      }`}
    >
      {/* Biểu tượng nguồn ngữ cảnh */}
      <span className="shrink-0 text-sm" aria-hidden>
        {isAlert ? "🚨" : "🔍"}
      </span>

      {/* Nhãn nguồn — ẩn trên màn nhỏ để giữ 1 dòng gọn */}
      <span className="hidden shrink-0 text-label uppercase text-ink/40 sm:inline">
        {isAlert ? "Cảnh báo" : "Phân tích"}
      </span>

      {/* Tiêu đề cụm — co giãn, cắt 1 dòng */}
      <span className="min-w-0 flex-1 truncate text-body-sm font-semibold text-ink">
        Cụm #{context.clusterId}
        {label ? ` · ${label}` : ""}
      </span>

      {/* Chỉ giữ pill mức độ (thông tin quan trọng nhất) */}
      {band && sevMax != null && (
        <span
          className="shrink-0 rounded-full px-2 py-0.5 text-caption font-medium text-ink"
          style={{ backgroundColor: `${bandColor(band)}33`, borderColor: bandColor(band), borderWidth: 1 }}
        >
          {sevMax}/10
        </span>
      )}

      <button
        type="button"
        onClick={onClear}
        aria-label="Bỏ ngữ cảnh"
        title="Bỏ ngữ cảnh"
        className="-mr-1 shrink-0 rounded-full px-1.5 py-0.5 text-lg leading-none text-ink/35 transition hover:bg-ink/5 hover:text-ink"
      >
        ×
      </button>
    </div>
  );
}
