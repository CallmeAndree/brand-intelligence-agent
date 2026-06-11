"use client";

import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import type { TopicItem } from "@/lib/types";

export default function TopicChart() {
  const { setDim } = useFilters();
  const { data, loading, error } = useStats<TopicItem[]>("/api/stats/topic", { limit: 15 });

  return (
    <Card title="Top chủ đề">
      <StatefulChart loading={loading} error={error} data={data} isEmpty={(d) => d.length === 0}>
        {(d) => {
          const items = [...d].reverse();
          const option = {
            tooltip: {
              trigger: "axis",
              axisPointer: { type: "shadow" },
              formatter: (ps: any[]) => {
                const i = ps[0];
                const it = items[i.dataIndex];
                return `${it.key}<br/>Số lượng: ${it.count}<br/>Severity TB: ${it.avg_severity}`;
              },
            },
            grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
            xAxis: { type: "value" },
            yAxis: {
              type: "category",
              data: items.map((x) => x.key),
              axisLabel: { fontSize: 10, width: 160, overflow: "truncate" },
            },
            series: [
              {
                type: "bar",
                data: items.map((x) => x.count),
                itemStyle: { color: "#b8a4ed", borderRadius: [0, 4, 4, 0] },
                barWidth: "60%",
              },
            ],
          };
          const onClick = (p: any) => {
            const key = items[p.dataIndex]?.key;
            if (key) setDim("topic", key);
          };
          return <EChart option={option} height={320} onEvents={{ click: onClick }} />;
        }}
      </StatefulChart>
    </Card>
  );
}
