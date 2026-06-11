"use client";

import { useStats } from "@/lib/useStats";
import type { KpiStats } from "@/lib/types";

function Kpi({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-card border border-ink/10 bg-white/60 p-4">
      <div className="text-xs uppercase tracking-wide text-ink/50">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${accent ?? "text-ink"}`}>{value}</div>
    </div>
  );
}

export default function KpiStrip() {
  const { data, loading, error } = useStats<KpiStats>("/api/stats/kpi");

  const k = data;
  const dash = loading ? "…" : error ? "—" : "0";

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
      <Kpi label="Tổng mention" value={k ? k.total.toLocaleString("vi-VN") : dash} />
      <Kpi label="% cần xử lý" value={k ? `${k.actionable_pct}%` : dash} />
      <Kpi label="Severity TB" value={k ? String(k.avg_severity) : dash} />
      <Kpi
        label="Critical (≥7)"
        value={k ? k.critical_count.toLocaleString("vi-VN") : dash}
        accent="text-error"
      />
      <Kpi
        label="Đang pending"
        value={k ? k.pending_count.toLocaleString("vi-VN") : dash}
        accent="text-warning"
      />
    </div>
  );
}
