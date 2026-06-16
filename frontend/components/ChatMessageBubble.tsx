"use client";

import type { ChatMessage, EChartSpec } from "@/lib/types";
import Markdown from "./Markdown";
import EChart from "./EChart";

// Palette Clay cho chart inline (đồng bộ dashboard: teal đậm + feature colors).
const CHAT_CHART_COLORS = ["#1a3a3a", "#ff6b5a", "#b8a4ed", "#e8a87c", "#d4a017"];

// Dựng option ECharts từ EChartSpec tối giản (backend RT1 get_trend/compare_periods).
function specToOption(spec: EChartSpec): Record<string, unknown> {
  const multi = spec.series.length > 1;
  return {
    color: CHAT_CHART_COLORS,
    title: spec.title
      ? { text: spec.title, left: "center", textStyle: { fontSize: 13, color: "#0a0a0a" } }
      : undefined,
    tooltip: { trigger: "axis" },
    legend: multi ? { bottom: 0, textStyle: { fontSize: 11 } } : undefined,
    grid: { left: 44, right: 16, top: spec.title ? 36 : 16, bottom: multi ? 32 : 24 },
    xAxis: { type: "category", data: spec.xAxis ?? [], axisLabel: { fontSize: 10 } },
    yAxis: { type: "value", axisLabel: { fontSize: 10 } },
    series: spec.series.map((s) => ({
      name: s.name,
      type: spec.type,
      data: s.data,
      smooth: spec.type === "line",
      barMaxWidth: 48,
    })),
  };
}

// Bong bóng hội thoại — design/DESIGN.md: 2 màu palette phân biệt vai, bo 16px.
// user → feature-teal (text trắng, phải, plain); assistant → surface cream (ink, trái, Markdown).
export default function ChatMessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-body-md ${
          isUser
            ? "whitespace-pre-wrap bg-feature-teal text-white"
            : "border border-ink/10 bg-feature-cream text-ink"
        }`}
      >
        {isUser ? message.text : <Markdown>{message.text}</Markdown>}

        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.citations.map((c, i) => (
              <a
                key={i}
                href={c.url}
                target="_blank"
                rel="noreferrer"
                className="rounded-full bg-white/70 px-2 py-0.5 text-caption text-ink/70 underline"
              >
                {c.author || c.source || "nguồn"}
              </a>
            ))}
          </div>
        )}
        {/* Chart inline cho câu trả lời từ tool chuỗi thời gian (get_trend/compare_periods). */}
        {!isUser && message.charts && message.charts.length > 0 && (
          <div className="mt-3 space-y-3">
            {message.charts.map((spec, i) => (
              <div key={i} className="rounded-xl border border-ink/10 bg-canvas/70 p-2">
                <EChart option={specToOption(spec)} height={240} downloadName={spec.title ?? "chart"} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
