"use client";
// 홈 화면에 앱으로 받는 법(설치형 웹앱 = 우리 전용 앱). 받기 화면(Landing, bare) · 설정 · 알림 켜기에서 보인다.
// 안드로이드 · PC 크롬: beforeinstallprompt 를 받아 '앱 설치' 버튼. 아이폰 · 아이패드 사파리: 공유 → 홈 화면에 추가 그림 안내.
// 이미 설치한 앱으로 열었으면(display-mode: standalone) 아무것도 보이지 않는다.
import { useEffect, useState } from "react";

type Prompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
type Mode = "none" | "prompt" | "ios" | "android";
export type Platform = "installed" | "ios" | "android" | "other";

// 지금 어디서 열었나(브라우저 밖에서만 부른다)
export function platform(): Platform {
  const nav = navigator as Navigator & { standalone?: boolean };
  if (matchMedia("(display-mode: standalone)").matches || nav.standalone) return "installed";
  const ua = nav.userAgent;
  if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && nav.maxTouchPoints > 1)) return "ios";
  return /Android/.test(ua) ? "android" : "other";
}

export default function InstallGuide({ bare }: { bare?: boolean }) {
  const [mode, setMode] = useState<Mode>("none");
  const [ev, setEv] = useState<Prompt | null>(null);

  useEffect(() => {
    const p = platform();
    if (p === "installed") return;
    if (p === "ios" || p === "android") setMode(p);
    const got = (e: Event) => { e.preventDefault(); setEv(e as Prompt); setMode("prompt"); };
    const done = () => setMode("none");
    addEventListener("beforeinstallprompt", got);
    addEventListener("appinstalled", done);
    return () => { removeEventListener("beforeinstallprompt", got); removeEventListener("appinstalled", done); };
  }, []);

  if (mode === "none") return null;
  const install = async () => {
    if (!ev) return;
    await ev.prompt();
    if ((await ev.userChoice).outcome === "accepted") setMode("none");
  };
  const body = mode === "prompt" ? <button className="primary" onClick={install}>홈 화면에 설치</button>
    : mode === "ios" ? (
      <ol className="steps-num">
        <li>사파리 아래 막대의 공유 버튼 <ShareIcon />을 눌러요.</li>
        <li>목록을 내려 <b>홈 화면에 추가</b>를 눌러요.</li>
        <li>오른쪽 위 <b>추가</b>를 눌러요.</li>
      </ol>
    ) : <p style={{ margin: 0 }}>크롬 오른쪽 위 메뉴(⋮)에서 <b>앱 설치</b>를 눌러요.</p>;
  if (bare) return body;
  return (
    <section className="card stack" aria-label="앱으로 받기">
      <h2>홈 화면에 앱으로 두기</h2>
      {body}
    </section>
  );
}

// 사파리 공유 버튼 모양(네모에서 위로 나가는 화살표)
function ShareIcon() {
  return (
    <svg role="img" aria-label="공유" width="18" height="22" viewBox="0 0 18 22" style={{ verticalAlign: "-4px" }}
      fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 14V2M5 5.5 9 1.5l4 4M6 9H3v11h12V9h-3" />
    </svg>
  );
}
