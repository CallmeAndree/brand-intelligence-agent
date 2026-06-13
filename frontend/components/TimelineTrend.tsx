"use client";

import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import type { TimelinePoint } from "@/lib/types";

// "2026-01" → { from: "2026-01-01", to: "2026-01-31" }; "2026-01-15" → from=to.
function labelToRange(label: string): { from: string; to: string } | null {
  const m = label.match(/^(\d{4})-(\d{2})$/);
  if (m) {
    const y = Number(m[1]);
    const mo = Number(m[2]);
    const last = new Date(Date.UTC(y, mo, 0)).getUTCDate();
    return {
      from: `${m[1]}-${m[2]}-01`,
      to: `${m[1]}-${m[2]}-${String(last).padStart(2, "0")}`,
    };
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(label)) return { from: label, to: label };
  return null;
}

export default function TimelineTrend() {
  const { setDateRange } = useFilters();
  const { data, loading, error } = useStats<{ points: TimelinePoint[] }>(
    "/api/stats/timeline",
    { bucket: "month" },
  );

  return (
    <Card title="Severity trung bình theo thời gian">
      <StatefulChart
        loading={loading}
        error={error}
        data={data}
        isEmpty={(d) => d.points.length === 0}
      >
        {(d) => {
          const dates = d.points.map((p) => p.date);
          const option = {
            tooltip: {
              trigger: "axis",
              valueFormatter: (value: number) => value.toFixed(1),
            },
            grid: { left: 48, right: 24, top: 24, bottom: 64 },
            xAxis: {
              type: "category",
              data: dates,
              axisLabel: { rotate: 45, fontSize: 10 },
            },
            yAxis: { type: "value", min: 0, max: 10, name: "Severity TB" },
            dataZoom: [
              { type: "slider", bottom: 30, height: 16 },
              { type: "inside" },
            ],
            series: [
              {
                name: "Severity TB",
                type: "line",
                smooth: true,
                symbol: "circle",
                symbolSize: 7,
                itemStyle: { color: "#1a3a3a" },
                lineStyle: { color: "#1a3a3a", width: 3 },
                areaStyle: { color: "rgba(184, 164, 237, 0.22)" },
                data: d.points.map((p) => p.avg),
                markLine: {
                  symbol: "none",
                  lineStyle: { color: "#d9534f", type: "dashed" },
                  label: { formatter: "Critical 7" },
                  data: [{ yAxis: 7 }],
                },
              },
            ],
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

          return (
            <EChart
              option={option}
              height={320}
              onEvents={{ datazoom: onDataZoom }}
            />
          );
        }}
      </StatefulChart>
    </Card>
  );
}
