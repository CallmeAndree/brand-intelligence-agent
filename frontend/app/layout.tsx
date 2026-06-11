import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Brand Intelligence — Dashboard",
  description: "Theo dõi & phân tích mention negative về Zalo/ZaloPay",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className="min-h-screen bg-canvas text-ink antialiased">{children}</body>
    </html>
  );
}
