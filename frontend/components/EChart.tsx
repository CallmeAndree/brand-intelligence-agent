"use client";

import dynamic from "next/dynamic";

// Wrapper ECharts layout-independent — nhận `option` THUẦN.
// Dùng chung cho dashboard + (sau này) render chart inline trong chat (Phương án 3).
const ReactECharts = dynamic(
  async () => {
    await import("echarts-wordcloud");
    return import("echarts-for-react");
  },
  { ssr: false },
);

export interface EChartProps {
  option: Record<string, unknown>;
  height?: number;
  // map event ECharts → handler (vd { click: (params) => ... }) cho cross-filter
  onEvents?: Record<string, (params: any) => void>;
}

export default function EChart({
  option,
  height = 300,
  onEvents,
}: EChartProps) {
  return (
    <ReactECharts
      option={option}
      style={{ height, width: "100%" }}
      opts={{ renderer: "canvas" }}
      notMerge
      onEvents={onEvents}
    />
  );
}
