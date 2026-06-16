// Font cho text trong chart (ECharts canvas) — phải KHỚP font app theo design/DESIGN.md:
// Aeonik Pro là font chính (fallback Inter). Canvas KHÔNG hiểu `var(--font-aeonik)`,
// nên ta đọc giá trị thật của CSS variable lúc runtime rồi dựng stack literal.
// Inter giữ làm fallback vì Aeonik thiếu một số dấu tiếng Việt.

const FALLBACK_STACK = '"Inter", ui-sans-serif, system-ui, sans-serif';

let cached: string | null = null;

/**
 * Trả về font-family literal dùng cho ECharts (Aeonik resolved + Inter fallback).
 * An toàn khi gọi lúc SSR/chưa mount → trả thẳng fallback Inter.
 */
export function getChartFontFamily(): string {
  if (cached) return cached;
  if (typeof document === "undefined") return FALLBACK_STACK;

  const aeonik = getComputedStyle(document.documentElement)
    .getPropertyValue("--font-aeonik")
    .trim();

  const stack = aeonik ? `${aeonik}, ${FALLBACK_STACK}` : FALLBACK_STACK;
  // chỉ cache khi đã resolve được Aeonik (tránh "khóa" fallback nếu chạy trước khi var sẵn sàng)
  if (aeonik) cached = stack;
  return stack;
}
