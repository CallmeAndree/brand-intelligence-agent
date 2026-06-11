"use client";

import { useState } from "react";
import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { SEVERITY_BANDS, bandColor, CATEGORICAL_PALETTE } from "@/lib/severity";
import type { TimelinePoint, TimelineGroupBy, SeverityBand } from "@/lib/types";

const BAND_ORDER: SeverityBand[] = ["low", "medium", "high", "critical"];

// "2026-01" → { from: "2026-01-01", to: "2026-01-31" }; "2026-01-15" → from=to.
function labelToRange(label: string): { from: string; to: string } | null {
  const m = label.match(/^(\d{4})-(\d{2})$/);
  if (m) {
    const y = Number(m[1]);
    const mo = Number(m[2]);
    const last = new Date(Date.UTC(y, mo, 0)).getUTCDate();
    return { from: `${m[1]}-${m[2]}-01`, to: `${m[1]}-${m[2]}-${String(last).padStart(2, "0")}` };
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(label)) return { from: label, to: label };
  return null;
}

export default function TimelineTrend() {
  const [groupBy, setGroupBy] = useState<TimelineGroupBy>("severityBand");
  const { setDateRange } = useFilters();
  const { data, loading, error } = useStats<{ points: TimelinePoint[]; series: string[] }>(
    "/api/stats/timeline",
    { bucket: "month", groupBy }
  );

  const toggle = (
    <div className="flex gap-1 text-xs">
      {(["severityBand", "platform", "topic"] as TimelineGroupBy[]).map((g) => (
        <button
          key={g}
          onClick={() => setGroupBy(g)}
          className={`rounded-full px-2.5 py-1 ${
            groupBy === g ? "bg-ink text-white" : "bg-feature-cream text-ink/70"
          }`}
        >
          {g === "severityBand" ? "Mức độ" : g === "platform" ? "Nền tảng" : "Chủ đề"}
        </button>
      ))}
    </div>
  );

  return (
    <Card title="Diễn biến theo thời gian" right={toggle}>
      <StatefulChart
        loading={loading}
        error={error}
        data={data}
        isEmpty={(d) => d.points.length === 0}
      >
        {(d) => {
          const dates = d.points.map((p) => p.date);
          // severityBand: theo thứ tự low→critical + màu band; khác: palette xoay vòng
          const series =
            groupBy === "severityBand"
              ? BAND_ORDER.filter((b) => d.series.includes(b))
              : d.series;

          const option = {
            tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
            legend: { bottom: 0, type: "scroll" },
            grid: { left: 48, right: 16, top: 12, bottom: 64 },
            xAxis: { type: "category", data: dates, axisLabel: { rotate: 45, fontSize: 10 } },
            yAxis: { type: "value" },
            dataZoom: [
              { type: "slider", bottom: 30, height: 16 },
              { type: "inside" },
            ],
            series: series.map((s, i) => ({
              name:
                groupBy === "severityBand"
                  ? SEVERITY_BANDS.find((b) => b.band === s)?.label ?? s
                  : s,
              type: "bar",
              stack: "total",
              emphasis: { focus: "series" },
              itemStyle: {
                color:
                  groupBy === "severityBand"
                    ? bandColor(s as SeverityBand)
                    : CATEGORICAL_PALETTE[i % CATEGORICAL_PALETTE.length],
              },
              data: d.points.map((p) => p[s] ?? 0),
            })),
          };

          // Brush dataZoom → set dateRange theo bucket đầu/cuối vùng chọn.
          const onDataZoom = (params: any) => {
            const z = params?.batch?.[0] ?? params;
            let startIdx = z?.startValue;
            let endIdx = z?.endValue;
            if (startIdx == null && typeof z?.start === "number") {
              startIdx = Math.floor((z.start / 100) * (dates.length - 1));
              endIdx = Math.ceil((z.end / 100) * (dates.length - 1));
            }
            if (startIdx == null || endIdx == null) return;
            const a = labelToRange(dates[Math.max(0, startIdx)]);
            const b = labelToRange(dates[Math.min(dates.length - 1, endIdx)]);
            if (a && b) setDateRange(a.from, b.to);
          };

          return <EChart option={option} height={320} onEvents={{ datazoom: onDataZoom }} />;
        }}
      </StatefulChart>
    </Card>
  );
}
