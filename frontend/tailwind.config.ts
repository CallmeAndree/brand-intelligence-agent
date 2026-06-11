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
          pink: "#ff4d8b",
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
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
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
