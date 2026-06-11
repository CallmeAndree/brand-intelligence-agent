"use client";

import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import type { CountItem } from "@/lib/types";

export default function ProductAreaBar() {
  const { setDim } = useFilters();
  const { data, loading, error } = useStats<CountItem[]>("/api/stats/product-area", { limit: 10 });

  return (
    <Card title="Top mảng sản phẩm">
      <StatefulChart loading={loading} error={error} data={data} isEmpty={(d) => d.length === 0}>
        {(d) => {
          // bar ngang: count tăng dần từ dưới lên (ECharts category y đảo)
          const items = [...d].reverse();
          const option = {
            tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
            grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
            xAxis: { type: "value" },
            yAxis: {
              type: "category",
              data: items.map((x) => x.key),
              axisLabel: { fontSize: 10, width: 140, overflow: "truncate" },
            },
            series: [
              {
                type: "bar",
                data: items.map((x) => x.count),
                itemStyle: { color: "#1a3a3a", borderRadius: [0, 4, 4, 0] },
                barWidth: "60%",
              },
            ],
          };
          const onClick = (p: any) => {
            const key = items[p.dataIndex]?.key;
            if (key) setDim("productArea", key);
          };
          return <EChart option={option} height={280} onEvents={{ click: onClick }} />;
        }}
      </StatefulChart>
    </Card>
  );
}
