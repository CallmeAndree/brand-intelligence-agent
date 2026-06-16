"use client";

import { useRouter } from "next/navigation";
import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { resetSession, queueExplainContext } from "@/lib/chat";
import type { TopicItem } from "@/lib/types";

export default function TopicChart() {
  const router = useRouter();
  const { filters, setDim, clearAll } = useFilters();
  const { data, loading, validating, error } = useStats<TopicItem[]>("/api/stats/topic", {
    limit: 10,
  });

  return (
    <Card
      title="Top chủ đề"
      subtitle="Số lượng mention theo chủ đề/cụm thảo luận, nhiều nhất xếp trên. Bấm một thanh để lọc."
    >
      <StatefulChart
        loading={loading}
        validating={validating}
        error={error}
        data={data}
        isEmpty={(d) => d.length === 0}
      >
        {(d) => {
          const items = [...d].reverse();
          const option = {
            tooltip: {
              trigger: "axis",
              axisPointer: { type: "shadow" },
              formatter: (ps: any[]) => {
                const i = ps[0];
                const it = items[i.dataIndex];
                const mode = it.mode === "cluster" ? "Cụm" : "Topic thô";
                return `${it.key}<br/>${mode}<br/>Số lượng: ${it.count}<br/>Avg Severity: ${it.avg_severity}`;
              },
            },
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
                itemStyle: { color: "#ffb084", borderRadius: [0, 4, 4, 0] },
                barWidth: "60%",
              },
            ],
          };
          const onClick = (p: any) => {
            const item = items[p.dataIndex];
            if (!item) return;
            if (item.mode === "cluster" && item.cluster_id)
              setDim("clusterId", item.cluster_id);
            else setDim("topic", item.key);
          };
          // Chuột phải một chủ đề/cụm → mở phiên Chat mới phân tích chủ đề đó.
          const onExplain = (p: any) => {
            const item = items[p.dataIndex];
            if (!item) return;
            resetSession();
            queueExplainContext({
              source: "dashboard",
              dimension: "topic",
              value: item.key,
              label: `Chủ đề "${item.key}"`,
              metric: { name: "Số mention", value: item.count },
              cluster_id:
                item.mode === "cluster" && item.cluster_id ? item.cluster_id : undefined,
              filters,
            });
            router.push("/chat");
          };
          return (
            <EChart
              option={option}
              height={400}
              onEvents={{ click: onClick }}
              onBlankClick={clearAll}
              onExplain={onExplain}
              downloadName="top-chu-de"
            />
          );
        }}
      </StatefulChart>
    </Card>
  );
}
