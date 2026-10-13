// 사이트 주소 · 공유 미리보기(OG · 트위터 카드) · 설치형 웹앱 연결. app/layout.tsx 가 metadata 로 쓴다.
// 도메인을 바꾸면 NEXT_PUBLIC_SITE_URL 하나만 바꾼다(robots.txt · sitemap.xml · og:url 이 따라감).
import type { Metadata } from "next";

export const SITE = (process.env.NEXT_PUBLIC_SITE_URL || "https://my-universe-seven.vercel.app").replace(/\/$/, "");
const title = "나의 우주";
const description = "일기를 쓰면 생각 단위로 나눠 나만의 우주에 띄우고, 별지기가 지난 기록을 기억해 말을 걸어요.";
const image = { url: "/og.jpg", width: 1200, height: 630, alt: "나의 우주 — 일기로 만든 우주 화면" };

export const siteMeta: Metadata = {
  metadataBase: new URL(SITE),
  title, description, applicationName: title,
  manifest: "/manifest.webmanifest",
  icons: { icon: [{ url: "/icons/icon.svg", type: "image/svg+xml" }, { url: "/icons/icon-192.png", sizes: "192x192" }], apple: "/icons/apple-touch-icon.png" },
  appleWebApp: { capable: true, title, statusBarStyle: "black" },
  openGraph: { type: "website", siteName: title, locale: "ko_KR", title, description, images: [image] },
  twitter: { card: "summary_large_image", title, description, images: [image.url] },
};
