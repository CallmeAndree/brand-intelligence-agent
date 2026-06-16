"use client";

import { useRouter } from "next/navigation";
import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { resetSession, queueExplainContext } from "@/lib/chat";
import type { RiskMatrixItem } from "@/lib/types";

// median của mảng số (đã sort tăng dần).
function median(values: number[]): number {
  if (values.length === 0) return 0;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

export default function RiskScatter() {
  const router = useRouter();
  const { filters, setDim, clearAll } = useFilters();
  const { data, loading, validating, error } = useStats<RiskMatrixItem[]>(
    "/api/stats/risk-matrix",
  );

  return (
    <Card
      title="Ma trận ưu tiên xử lý"
      subtitle="Mỗi bong bóng là một mảng sản phẩm: trục ngang = số lượng mention, trục dọc = mức độ nghiêm trọng TB. Góc phải trên (nhiều + nặng) = ưu tiên xử lý cao nhất."
    >
      <StatefulChart
        loading={loading}
        validating={validating}
        error={error}
        data={data}
        isEmpty={(d) => d.length === 0}
      >
        {(items) => {
          const maxVol = Math.max(...items.map((x) => x.volume), 1);
          const medVol = median(items.map((x) => x.volume));
          const option = {
            tooltip: {
              trigger: "item",
              formatter: (p: any) => {
                const it = items[p.dataIndex];
                return `${it.key}<br/>Số lượng: ${it.volume}<br/>Avg Severity: ${it.sev}`;
              },
            },
            grid: { left: 8, right: 24, top: 16, bottom: 32, containLabel: true },
            xAxis: { type: "value", name: "Số lượng", nameGap: 22, min: 0 },
            yAxis: { type: "value", name: "Avg Severity", min: 0, max: 10 },
            series: [
              {
                type: "scatter",
                // size bong bóng ∝ volume (12–60px theo tỉ lệ với max).
                symbolSize: (val: number[]) => 12 + (val[0] / maxVol) * 48,
                data: items.map((x) => ({
                  value: [x.volume, x.sev],
                  // góc ưu tiên (volume cao + sev ≥ 7) tô coral, còn lại lavender — không shadow.
                  itemStyle: {
                    color:
                      x.sev >= 7 && x.volume >= medVol ? "#ff6b5a" : "#b8a4ed",
                    opacity: 0.78,
                  },
                })),
                markLine: {
                  symbol: "none",
                  silent: true,
                  lineStyle: { color: "#ef4444", type: "dashed" },
                  // nhãn nằm TRONG grid (insideEndTop) → không tràn mép bị xén; mỗi đường 1 nhãn riêng
                  label: { position: "insideEndTop" },
                  data: [
                    { yAxis: 7, label: { formatter: "Critical 7", color: "#ef4444" } },
                    {
                      xAxis: medVol,
                      lineStyle: { color: "#1a3a3a" },
                      label: { formatter: "Trung vị", color: "#1a3a3a" },
                    },
                  ],
                },
              },
            ],
          };
          const onClick = (p: any) => {
            const key = items[p.dataIndex]?.key;
            if (key) setDim("productArea", key);
          };
          // Chuột phải một bong bóng → mở phiên Chat mới luận vị trí ưu tiên (volume × severity TB).
          const onExplain = (p: any) => {
            const it = items[p.dataIndex];
            if (!it) return;
            resetSession();
            queueExplainContext({
              source: "dashboard",
              dimension: "risk",
              value: it.key,
              label: `Mảng ${it.key}`,
              metric: { name: "Số lượng", value: it.volume },
              metric2: { name: "Avg Severity", value: it.sev },
              filters,
            });
            router.push("/chat");
          };
          return <EChart option={option} height={400} onEvents={{ click: onClick }} onBlankClick={clearAll} onExplain={onExplain} downloadName="ma-tran-uu-tien" />;
        }}
      </StatefulChart>
    </Card>
  );
}
