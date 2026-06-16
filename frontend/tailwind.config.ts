import type { Config } from "tailwindcss";

// Palette bám design/DESIGN.md (Clay-style). KHÔNG dark mode.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#fffaf0", // nền cream — bắt buộc
        ink: "#0a0a0a", // near-black (primary/CTA, text)
        // 6 feature colors
        feature: {
          blue: "#0068ff", // xanh dương thương hiệu Zalopay (thay màu hồng cũ)
          teal: "#1a3a3a",
          lavender: "#b8a4ed",
          peach: "#ffb084",
          ochre: "#e8b94a",
          cream: "#f5f0e0",
        },
        // semantic
        success: "#22c55e",
        warning: "#f59e0b",
        error: "#ef4444",
      },
      fontFamily: {
        sans: [
          "var(--font-aeonik)",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
      },
      // Thang typography bám design/DESIGN.md (token = [size, {lineHeight, letterSpacing, fontWeight}]).
      // Weight chỉ bake vào token có weight cố định (display/title/button/label/nav);
      // body/caption để weight mặc định (400) cho caller tự thêm khi cần.
      fontSize: {
        "display-md": ["40px", { lineHeight: "1.1", letterSpacing: "-1px", fontWeight: "500" }],
        "display-sm": ["32px", { lineHeight: "1.15", letterSpacing: "-0.5px", fontWeight: "500" }],
        "title-lg": ["24px", { lineHeight: "1.3", letterSpacing: "-0.3px", fontWeight: "600" }],
        "title-md": ["18px", { lineHeight: "1.4", fontWeight: "600" }],
        "title-sm": ["16px", { lineHeight: "1.4", fontWeight: "600" }],
        "body-md": ["16px", { lineHeight: "1.55" }],
        "body-sm": ["14px", { lineHeight: "1.55" }],
        caption: ["13px", { lineHeight: "1.4" }],
        label: ["12px", { lineHeight: "1.4", letterSpacing: "1.5px", fontWeight: "600" }],
        button: ["14px", { lineHeight: "1", fontWeight: "600" }],
        nav: ["14px", { lineHeight: "1.4", fontWeight: "500" }],
      },
      borderRadius: {
        card: "16px",
        feature: "24px",
      },
      maxWidth: {
        content: "1280px",
      },
    },
  },
  plugins: [],
};

export default config;
