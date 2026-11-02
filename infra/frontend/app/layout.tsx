import type { Viewport } from "next";
import { IBM_Plex_Mono, Poor_Story } from "next/font/google";
import Shell from "@/components/Shell";
import { siteMeta } from "@/lib/site";
import "./globals.css";

export const metadata = siteMeta; // 공유 미리보기 · manifest · 아이콘(lib/site.ts)
// 일기장 글꼴 = 푸어스토리: 컴퓨터 글자처럼 반듯하되 손글씨 느낌이 조금(2026-11-02 동규 「나눔펜은 정신없음」, 일기 종이 위 글에만, globals.css --font-diary). 빌드할 때 받아 우리 서버에서 내보낸다(화면에서 구글에 묻지 않음).
// 한글은 글자 묶음(unicode-range) 여러 개라 미리 받지 않고(preload: false) 쓰기 화면에서 쓸 때 받는다.
const diary = Poor_Story({ weight: "400", variable: "--font-diary", display: "swap", preload: false });
// 숫자 글꼴(달력 날짜): 받기 화면과 같은 고정폭(부가티 느낌, 2026-11-03). 라틴 글자만이라 작다
const num = IBM_Plex_Mono({ weight: "400", subsets: ["latin"], variable: "--font-num" });

// 홈 화면 앱(전용 앱)으로 열면 상태 막대 밑까지 화면을 쓴다(viewportFit cover). 머리줄 · 아래 탭이 안전 영역만큼 비켜 선다(globals.css --top-h · --tab-h)
export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#141414" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className={`${diary.variable} ${num.variable}`}>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
