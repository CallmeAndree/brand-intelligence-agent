"use client";

import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import type { CountItem } from "@/lib/types";

export default function ProductAreaBar() {
  const { setDim } = useFilters();
  const { data, loading, error } = useStats<CountItem[]>(
    "/api/stats/product-area",
    { limit: 10 },
  );

  return (
    <Card title="Top mảng sản phẩm">
      <StatefulChart
        loading={loading}
        error={error}
        data={data}
        isEmpty={(d) => d.length === 0}
      >
        {(items) => {
          const option = {
            tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
            grid: {
              left: 40,
              right: 16,
              top: 16,
              bottom: 72,
              containLabel: true,
            },
            xAxis: {
              type: "category",
              data: items.map((x) => x.key),
              axisLabel: {
                fontSize: 10,
                rotate: 35,
                width: 90,
                overflow: "truncate",
              },
            },
            yAxis: { type: "value" },
            series: [
              {
                type: "bar",
                data: items.map((x) => x.count),
                itemStyle: { color: "#1a3a3a", borderRadius: [4, 4, 0, 0] },
                barWidth: "55%",
              },
            ],
          };
          const onClick = (p: any) => {
            const key = items[p.dataIndex]?.key;
            if (key) setDim("productArea", key);
          };
          return (
            <EChart
              option={option}
              height={280}
              onEvents={{ click: onClick }}
            />
          );
        }}
      </StatefulChart>
    </Card>
  );
}
