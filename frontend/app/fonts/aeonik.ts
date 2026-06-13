import localFont from "next/font/local";

// Aeonik Pro — font chính của front-end (thay Inter).
// Inter giữ làm fallback vì Aeonik thiếu một số dấu tiếng Việt.
export const aeonik = localFont({
  src: [
    { path: "./AeonikPro-Light.otf", weight: "300", style: "normal" },
    { path: "./AeonikPro-LightItalic.otf", weight: "300", style: "italic" },
    { path: "./AeonikPro-Regular.otf", weight: "400", style: "normal" },
    { path: "./AeonikPro-RegularItalic.otf", weight: "400", style: "italic" },
    { path: "./AeonikPro-Medium.otf", weight: "500", style: "normal" },
    { path: "./AeonikPro-MediumItalic.otf", weight: "500", style: "italic" },
    { path: "./AeonikPro-Bold.otf", weight: "700", style: "normal" },
    { path: "./AeonikPro-BoldItalic.otf", weight: "700", style: "italic" },
    { path: "./AeonikPro-Black.otf", weight: "900", style: "normal" },
    { path: "./AeonikPro-BlackItalic.otf", weight: "900", style: "italic" },
  ],
  display: "swap",
  variable: "--font-aeonik",
  fallback: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
});
