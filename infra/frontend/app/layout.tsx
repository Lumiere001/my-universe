import type { Viewport } from "next";
import { Gowun_Batang } from "next/font/google";
import Shell from "@/components/Shell";
import { siteMeta } from "@/lib/site";
import "./globals.css";

export const metadata = siteMeta; // 공유 미리보기 · manifest · 아이콘(lib/site.ts)
// 일기장 글꼴(쓰기 화면 일기 본문에만, globals.css --font-diary). 빌드할 때 받아 우리 서버에서 내보낸다(화면에서 구글에 묻지 않음).
// 한글은 글자 묶음(unicode-range) 여러 개라 미리 받지 않고(preload: false) 쓰기 화면에서 쓸 때 받는다.
const diary = Gowun_Batang({ weight: ["400", "700"], variable: "--font-diary", display: "swap", preload: false });

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#1e1e1e" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className={diary.variable}>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
