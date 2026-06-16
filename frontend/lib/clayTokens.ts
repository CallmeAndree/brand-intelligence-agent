// Hằng màu Clay dùng cho HTML string trong ECharts (tooltip/nút) — nơi Tailwind class
// KHÔNG áp được. Đây là NGOẠI LỆ DUY NHẤT được phép inline hex; mọi giá trị PHẢI khớp
// chính xác token trong `design/DESIGN.md` + `tailwind.config.ts` (D7). Khai báo tập
// trung tại đây để không rải magic-hex khắp các chart.
export const CLAY = {
  ink: "#0a0a0a", // nền nút primary / chữ thường
  primaryActive: "#1f1f1f", // trạng thái nhấn nút
  onPrimary: "#ffffff", // chữ trên nút primary
  canvas: "#fffaf0", // nền tooltip (cream)
  hairline: "#e5e5e5", // viền tooltip/hairline
  lavender: "#b8a4ed", // accent ngữ cảnh AI (banner dashboard)
  body: "#3a3a3a", // chữ phụ trong tooltip
} as const;
