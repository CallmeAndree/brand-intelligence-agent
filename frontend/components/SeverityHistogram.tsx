"use client";

import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { SEVERITY_BANDS } from "@/lib/severity";
import type { CountItem, SeverityBand } from "@/lib/types";

export default function SeverityHistogram() {
  const { setDim } = useFilters();
  const { data, loading, error } = useStats<CountItem[]>("/api/stats/severity");

  return (
    <Card title="Phân bố mức độ nghiêm trọng">
      <StatefulChart
        loading={loading}
        error={error}
        data={data}
        isEmpty={(d) => d.every((x) => x.count === 0)}
      >
        {(d) => {
          const option = {
            tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
            grid: { left: 48, right: 16, top: 12, bottom: 30 },
            xAxis: {
              type: "category",
              data: d.map((x) => SEVERITY_BANDS.find((b) => b.band === x.key)?.label ?? x.key),
              axisLabel: { fontSize: 10 },
            },
            yAxis: { type: "value" },
            series: [
              {
                type: "bar",
                data: d.map((x) => ({
                  value: x.count,
                  itemStyle: { color: SEVERITY_BANDS.find((b) => b.band === x.key)?.color },
                })),
                barWidth: "55%",
              },
            ],
          };
          const onClick = (p: any) => {
            const band = d[p.dataIndex]?.key as SeverityBand;
            if (band) setDim("severityBand", band);
          };
          return <EChart option={option} height={260} onEvents={{ click: onClick }} />;
        }}
      </StatefulChart>
    </Card>
  );
}
