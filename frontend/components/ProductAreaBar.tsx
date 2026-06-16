"use client";

import { useRouter } from "next/navigation";
import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { resetSession, queueExplainContext } from "@/lib/chat";
import type { CountItem } from "@/lib/types";

export default function ProductAreaBar() {
  const router = useRouter();
  const { filters, setDim, clearAll } = useFilters();
  const { data, loading, validating, error } = useStats<CountItem[]>(
    "/api/stats/product-area",
    { limit: 10 },
  );

  // Chuột phải một cột mảng sản phẩm → mở phiên Chat phân tích mảng đó.
  const onExplain = (p: any) => {
    const value = String(p?.name ?? "");
    if (!value) return;
    resetSession();
    queueExplainContext({
      source: "dashboard",
      dimension: "product_area",
      value,
      label: `Mảng ${value}`,
      metric: { name: "Số mention", value: Number(p?.value ?? 0) },
      filters,
    });
    router.push("/chat");
  };

  return (
    <Card
      title="Top mảng sản phẩm"
      subtitle="Số lượng mention theo mảng sản phẩm bị nhắc tới, nhiều nhất xếp trên. Bấm một thanh để lọc."
    >
      <StatefulChart
        loading={loading}
        validating={validating}
        error={error}
        data={data}
        isEmpty={(d) => d.length === 0}
      >
        {(d) => {
          // Bar ngang giống TopicChart: category trên trục Y, count trên X, reverse để top ở trên.
          const items = [...d].reverse();
          const option = {
            tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
            grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
            xAxis: { type: "value" },
            yAxis: {
              type: "category",
              data: items.map((x) => x.key),
              axisLabel: { fontSize: 10, width: 260, overflow: "truncate" },
            },
            series: [
              {
                type: "bar",
                data: items.map((x) => x.count),
                itemStyle: { color: "#e8b94a", borderRadius: [0, 4, 4, 0] },
                barWidth: "60%",
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
              height={400}
              onEvents={{ click: onClick }}
              onBlankClick={clearAll}
              onExplain={onExplain}
              downloadName="top-mang-san-pham"
            />
          );
        }}
      </StatefulChart>
    </Card>
  );
}
