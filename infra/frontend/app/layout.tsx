import type { Metadata, Viewport } from "next";
import Shell from "@/components/Shell";
import "./globals.css";

export const metadata: Metadata = { title: "나의 우주", description: "생각 단위로 나눠 우주로 보여 주고 말을 거는 일기장" };
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
