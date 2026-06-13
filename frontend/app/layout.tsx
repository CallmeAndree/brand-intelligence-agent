import type { Metadata } from "next";
import { aeonik } from "./fonts/aeonik";
import TabNav from "@/components/TabNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Brand Intelligence — Dashboard",
  description: "Theo dõi & phân tích mention negative về ZaloPay",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi" className={aeonik.variable}>
      <body className="min-h-screen bg-canvas text-ink antialiased">
        <TabNav />
        {children}
      </body>
    </html>
  );
}
