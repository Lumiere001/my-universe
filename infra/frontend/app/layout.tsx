import type { Viewport } from "next";
import Shell from "@/components/Shell";
import { siteMeta } from "@/lib/site";
import "./globals.css";

export const metadata = siteMeta; // 공유 미리보기 · manifest · 아이콘(lib/site.ts)
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#07102a" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
