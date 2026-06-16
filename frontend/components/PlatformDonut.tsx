"use client";

import { useRouter } from "next/navigation";
import EChart from "./EChart";
import { Card, StatefulChart } from "./ui";
import { useStats } from "@/lib/useStats";
import { useFilters } from "@/lib/filters";
import { resetSession, queueExplainContext } from "@/lib/chat";
import { CATEGORICAL_PALETTE } from "@/lib/severity";
import type { CountItem } from "@/lib/types";

export default function PlatformDonut() {
  const router = useRouter();
  const { filters, setDim, clearAll } = useFilters();
  const { data, loading, validating, error } = useStats<CountItem[]>("/api/stats/platform");

  // Chuột phải một lát nền tảng → mở phiên Chat phân tích nền tảng đó.
  const onExplain = (p: any) => {
    const value = String(p?.name ?? "");
    if (!value || value === "unknown") return;
    const pct = p?.percent != null ? ` (${p.percent}%)` : "";
    resetSession();
    queueExplainContext({
      source: "dashboard",
      dimension: "platform",
      value,
      label: `Nền tảng ${value}`,
      metric: { name: `Số mention${pct}`, value: Number(p?.value ?? 0) },
      filters,
    });
    router.push("/chat");
  };

  return (
    <Card
      title="Phân bố nền tảng"
      subtitle="Tỷ trọng mention theo nền tảng mạng xã hội. Bấm một phần để lọc."
    >
      <StatefulChart
        loading={loading}
        validating={validating}
        error={error}
        data={data}
        isEmpty={(d) => d.length === 0}
      >
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
                // TikTok luôn dùng màu cyan đặc trưng, bất kể vị trí trong data; nền tảng khác theo palette.
                data: d.map((x) => ({
                  name: x.key,
                  value: x.count,
                  ...(/tiktok/i.test(x.key) ? { itemStyle: { color: "#00f2ea" } } : {}),
                })),
              },
            ],
          };
          const onClick = (p: any) => {
            if (p.name && p.name !== "unknown") setDim("platform", p.name);
          };
          return <EChart option={option} height={320} onEvents={{ click: onClick }} onBlankClick={clearAll} onExplain={onExplain} downloadName="phan-bo-nen-tang" />;
        }}
      </StatefulChart>
    </Card>
  );
}
