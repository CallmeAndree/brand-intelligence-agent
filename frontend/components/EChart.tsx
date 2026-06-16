"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef } from "react";
import { getChartFontFamily } from "@/lib/chartFont";
import { CLAY } from "@/lib/clayTokens";

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
  // khi set → hiện nút tải PNG (góc trên-phải), tên file = `${downloadName}.png`
  downloadName?: string;
  // click vào VÙNG TRỐNG của chart (không trúng điểm/cột) → gọi để bỏ filter
  onBlankClick?: () => void;
  // khi set → CHUỘT PHẢI (contextmenu) một điểm/cột/lát → gọi với params data point đó
  // để mở phiên Chat phân tích. Click đơn vẫn lọc như cũ (KHÔNG ảnh hưởng cross-filter);
  // chuột phải tách bạch hẳn click trái → hết nhập nhằng với double-click.
  onExplain?: (params: any) => void;
}

// Dòng gợi ý "Chuột phải để Giải thích" đính dưới tooltip — affordance cho thao tác
// chuột phải (thay nút cũ). Inline hex là ngoại lệ DUY NHẤT cho HTML ECharts
// (Tailwind không áp được) — khớp token CLAY.
const EXPLAIN_HINT_HTML =
  `<div style="margin-top:6px;padding-top:6px;border-top:1px solid ${CLAY.hairline};` +
  `font-size:12px;line-height:1.3;color:${CLAY.body};">✨ Chuột phải để Giải thích</div>`;

// Marker chấm màu series mà ECharts cấp sẵn (HTML span); fallback chuỗi rỗng.
function markerOf(p: any): string {
  return typeof p?.marker === "string" ? p.marker : "";
}

// Dựng lại nội dung tooltip mặc định (item/axis) rồi đính dòng gợi ý chuột phải — giữ
// value/label như cũ. valueFormatter (nếu chart khai báo) được áp để số khớp chart (vd severity .toFixed(1)).
function buildExplainTooltip(
  params: any,
  valueFormatter?: (v: any) => string,
): string {
  const fmt = (v: any) =>
    valueFormatter && typeof v === "number" ? valueFormatter(v) : `${v}`;
  let content: string;
  if (Array.isArray(params)) {
    // trigger "axis": header nhãn trục + từng series. Bỏ "tên series: " khi series
    // không đặt name (vd bar 1 series) để không dư dấu ":".
    const head = params[0]?.axisValueLabel ?? params[0]?.name ?? "";
    const rows = params
      .map((p) => `${markerOf(p)}${p.seriesName ? `${p.seriesName}: ` : ""}<b>${fmt(p.value)}</b>`)
      .join("<br/>");
    content = `${head ? `${head}<br/>` : ""}${rows}`;
  } else {
    // trigger "item": pie/scatter — name + value (+ % nếu có).
    const pct = params?.percent != null ? ` (${params.percent}%)` : "";
    content = `${markerOf(params)}${params?.name ?? ""}: <b>${fmt(params?.value)}</b>${pct}`;
  }
  return `${content}${EXPLAIN_HINT_HTML}`;
}

export default function EChart({
  option,
  height = 300,
  onEvents,
  downloadName,
  onBlankClick,
  onExplain,
}: EChartProps) {
  // Áp font app (Aeonik + Inter fallback) làm textStyle gốc cho MỌI chart — đồng bộ design.
  // Đặt ở root option → tất cả trục/legend/tooltip/title kế thừa; option tự set vẫn override được.
  const themed = useMemo(() => {
    const fontFamily = getChartFontFamily();
    const existing = (option.textStyle as Record<string, unknown> | undefined) ?? {};
    const base = { ...option, textStyle: { fontFamily, ...existing } };
    if (!onExplain) return base;
    // Bật explain: theme Clay tooltip (cream, hairline, không shadow nặng — D8) + formatter
    // đính dòng gợi ý "Chuột phải để Giải thích" (giữ value/label). Áp đồng nhất cho mọi chart.
    const prevTip = (option.tooltip as Record<string, any> | undefined) ?? {};
    const valueFormatter = prevTip.valueFormatter as ((v: any) => string) | undefined;
    // formatter ECharts có thể là FUNCTION (TopicChart/KeywordCloud/RiskScatter) HOẶC
    // STRING template (PlatformDonut: "{b}: {c} ({d}%)") — phải xử lý cả hai, nếu không
    // gọi string như hàm sẽ ném runtime "is not a function".
    const prevFormatter = prevTip.formatter as
      | ((p: any) => string)
      | string
      | undefined;
    // Chart đã khai báo formatter riêng → BỌC: giữ nguyên nội dung gốc rồi nối dòng gợi ý.
    // Chỉ khi chart không có formatter mới dùng buildExplainTooltip (dựng lại item/axis mặc định).
    let formatter: ((params: any) => string) | string;
    if (typeof prevFormatter === "function") {
      // gán vào const trong nhánh đã narrow → closure giữ kiểu (không "possibly undefined")
      const pf = prevFormatter;
      formatter = (params: any) => `${pf(params)}${EXPLAIN_HINT_HTML}`;
    } else if (typeof prevFormatter === "string") {
      // string template render như HTML → nối thẳng dòng gợi ý (token {b}/{c}/{d} vẫn được thay)
      formatter = `${prevFormatter}${EXPLAIN_HINT_HTML}`;
    } else {
      formatter = (params: any) => buildExplainTooltip(params, valueFormatter);
    }
    return {
      ...base,
      tooltip: {
        ...prevTip,
        backgroundColor: CLAY.canvas,
        borderColor: CLAY.hairline,
        borderWidth: 1,
        borderRadius: 12,
        textStyle: { color: CLAY.ink, fontFamily },
        extraCssText: "box-shadow:0 1px 2px rgba(10,10,10,0.06);padding:8px 10px;",
        formatter,
      },
    };
  }, [option, onExplain]);

  // giữ instance ECharts qua onChartReady để xuất ảnh (getDataURL)
  const instanceRef = useRef<any>(null);
  // giữ callback mới nhất trong ref → đăng ký zrender/contextmenu 1 lần, không re-bind mỗi render
  const blankClickRef = useRef(onBlankClick);
  useEffect(() => {
    blankClickRef.current = onBlankClick;
  }, [onBlankClick]);
  const onExplainRef = useRef(onExplain);
  useEffect(() => {
    onExplainRef.current = onExplain;
  }, [onExplain]);

  const handleDownload = () => {
    const chart = instanceRef.current;
    if (!chart) return;
    // nền canvas cream theo design (#fffaf0) thay vì trong suốt; pixelRatio 2 cho ảnh nét
    const url = chart.getDataURL({
      type: "png",
      pixelRatio: 2,
      backgroundColor: "#fffaf0",
    });
    const a = document.createElement("a");
    a.href = url;
    a.download = `${downloadName ?? "chart"}.png`;
    a.click();
  };

  return (
    <div className="relative">
      {downloadName && (
        <button
          type="button"
          onClick={handleDownload}
          aria-label="Tải biểu đồ về (PNG)"
          title="Tải biểu đồ về (PNG)"
          className="absolute right-0 top-0 z-10 flex h-7 w-7 items-center justify-center rounded-full border border-ink/10 bg-canvas/80 text-ink/50 backdrop-blur transition hover:bg-feature-cream hover:text-ink"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
        </button>
      )}
      <ReactECharts
        option={themed}
        style={{ height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        onEvents={onEvents}
        onChartReady={(chart: any) => {
          instanceRef.current = chart;
          // zrender click: e.target rỗng = click vùng trống (không trúng series) → bỏ filter.
          // Click trúng điểm/cột vẫn để onEvents.click xử lý (setDim) như cũ.
          chart.getZr().on("click", (e: any) => {
            if (!e.target) blankClickRef.current?.();
          });
          // CHUỘT PHẢI trúng một điểm/cột/lát → Giải thích (data point đó). CHỈ nhận series
          // item (bỏ qua contextmenu vào legend/trục → tránh value rỗng sinh "0 mention");
          // click trái vẫn để onEvents.click lo cross-filter như cũ — chuột phải tách bạch hẳn.
          chart.on("contextmenu", (p: any) => {
            if (p?.componentType === "series") {
              // chặn menu chuột phải mặc định của trình duyệt khi trúng data point
              p?.event?.event?.preventDefault?.();
              onExplainRef.current?.(p);
            }
          });
          // Chặn menu mặc định trên TOÀN vùng chart khi explain bật (kể cả vùng trống/trục)
          // để chuột phải luôn là affordance "Giải thích", không bật menu trình duyệt.
          chart.getZr().on("contextmenu", (e: any) => {
            if (onExplainRef.current) e?.event?.preventDefault?.();
          });
        }}
      />
    </div>
  );
}
