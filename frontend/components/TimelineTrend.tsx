"use client";

import { useRouter } from "next/navigation";
import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { resetSession, queueExplainContext } from "@/lib/chat";
import type { TimelinePoint } from "@/lib/types";

// "2026-01" → "Tháng 01/2026" (nhãn hiển thị cho banner/prompt).
function monthLabel(value: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(value);
  return m ? `Tháng ${m[2]}/${m[1]}` : value;
}

export default function TimelineTrend() {
  const router = useRouter();
  const { filters, clearAll } = useFilters();
  const { data, loading, validating, error } = useStats<{ points: TimelinePoint[] }>(
    "/api/stats/timeline",
    { bucket: "month" },
  );

  // Chuột phải một điểm tháng → mở phiên Chat mới phân tích severity tháng đó.
  const onExplain = (p: any) => {
    const value = String(p?.name ?? "");
    if (!value) return;
    // p.value của line series luôn là số; coerce + làm tròn 1 chữ số, fallback 0 để
    // không rò "undefined"/NaN vào prompt explain + banner (khớp PlatformDonut/ProductAreaBar).
    const raw = typeof p?.value === "number" ? p.value : Number(p?.value);
    const avg = Number.isFinite(raw) ? Number(raw.toFixed(1)) : 0;
    resetSession();
    queueExplainContext({
      source: "dashboard",
      dimension: "month",
      value,
      label: monthLabel(value),
      metric: { name: "Avg Severity", value: avg },
      filters,
    });
    router.push("/chat");
  };

  return (
    <Card
      title="Severity trung bình theo thời gian"
      subtitle="Mức độ nghiêm trọng TB của mention theo từng tháng; đường gạch ngang là Avg Severity toàn kỳ — tháng vượt đường này là cao hơn mặt bằng chung."
    >
      <StatefulChart
        loading={loading}
        validating={validating}
        error={error}
        data={data}
        isEmpty={(d) => d.points.length === 0}
      >
        {(d) => {
          const dates = d.points.map((p) => p.date);
          // severity trung bình toàn kỳ → đường ngang tham chiếu (thay mốc cứng 7).
          const overallAvg = d.points.length
            ? d.points.reduce((s, p) => s + p.avg, 0) / d.points.length
            : 0;
          const option = {
            tooltip: {
              trigger: "axis",
              valueFormatter: (value: number) => value.toFixed(1),
            },
            // containLabel: nhãn trục (gồm label tháng xoay 45°) luôn nằm trong grid → không bị xén.
            grid: { left: 8, right: 28, top: 28, bottom: 8, containLabel: true },
            xAxis: {
              type: "category",
              data: dates,
              axisLabel: { rotate: 45, fontSize: 10, hideOverlap: true },
            },
            yAxis: {
              type: "value",
              min: 0,
              max: 10,
              name: "Avg Severity",
              // căn trái + nằm trong grid để tên trục không bị xén ở mép
              nameLocation: "end",
              nameGap: 14,
              nameTextStyle: { align: "left", padding: [0, 0, 0, 4] },
            },
            series: [
              {
                name: "Avg Severity",
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
                  silent: true,
                  lineStyle: { color: "#d9534f", type: "dashed" },
                  // đặt nhãn NẰM TRONG grid (insideEndTop) → không tràn ra ngoài bị xén
                  label: {
                    formatter: `Avg Severity ${overallAvg.toFixed(1)}`,
                    position: "insideEndTop",
                    color: "#d9534f",
                  },
                  data: [{ yAxis: overallAvg }],
                },
              },
            ],
          };

          return <EChart option={option} height={320} onBlankClick={clearAll} onExplain={onExplain} downloadName="severity-theo-thoi-gian" />;
        }}
      </StatefulChart>
    </Card>
  );
}
