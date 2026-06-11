"use client";

import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { CATEGORICAL_PALETTE } from "@/lib/severity";
import type { CountItem } from "@/lib/types";

export default function PlatformDonut() {
  const { setDim } = useFilters();
  const { data, loading, error } = useStats<CountItem[]>("/api/stats/platform");

  return (
    <Card title="Phân bố nền tảng">
      <StatefulChart loading={loading} error={error} data={data} isEmpty={(d) => d.length === 0}>
        {(d) => {
          const option = {
            tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
            legend: { type: "scroll", bottom: 0 },
            color: CATEGORICAL_PALETTE,
            series: [
              {
                type: "pie",
                radius: ["45%", "70%"],
                center: ["50%", "45%"],
                avoidLabelOverlap: true,
                label: { show: false },
                data: d.map((x) => ({ name: x.key, value: x.count })),
              },
            ],
          };
          const onClick = (p: any) => {
            if (p.name && p.name !== "unknown") setDim("platform", p.name);
          };
          return <EChart option={option} height={280} onEvents={{ click: onClick }} />;
        }}
      </StatefulChart>
    </Card>
  );
}
