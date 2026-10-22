"use client";
// 홈 화면에 설치 안내(설치형 웹앱). 소개 화면 · 설정 화면에서 보인다.
// 안드로이드 · PC 크롬: beforeinstallprompt 를 받아 '앱 설치' 버튼. 아이폰 · 아이패드 사파리: 공유 → 홈 화면에 추가 그림 안내.
// 이미 설치한 앱으로 열었으면(display-mode: standalone) 아무것도 보이지 않는다.
import { useEffect, useState } from "react";

type Prompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
type Mode = "none" | "prompt" | "ios" | "android";

export default function InstallGuide() {
  const [mode, setMode] = useState<Mode>("none");
  const [ev, setEv] = useState<Prompt | null>(null);

  useEffect(() => {
    const nav = navigator as Navigator & { standalone?: boolean };
    if (matchMedia("(display-mode: standalone)").matches || nav.standalone) return;
    const ua = nav.userAgent;
    if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && nav.maxTouchPoints > 1)) setMode("ios");
    else if (/Android/.test(ua)) setMode("android");
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
  return (
    <section className="card stack" aria-label="앱으로 설치">
      <h2>홈 화면에 앱으로 두기</h2>
      {mode === "prompt" ? (
        <>
          <p className="sub" style={{ margin: 0 }}>스토어 없이 바로 설치돼요. 앱처럼 전체 화면으로 열려요.</p>
          <button className="primary" onClick={install}>홈 화면에 설치</button>
        </>
      ) : mode === "ios" ? (
        <ol style={{ margin: 0, paddingLeft: 20 }}>
          <li>사파리 아래(아이패드는 위) 막대의 공유 버튼 <ShareIcon />을 눌러요.</li>
          <li>목록을 내려 <b>&apos;홈 화면에 추가&apos;</b>를 눌러요.</li>
          <li>오른쪽 위 <b>&apos;추가&apos;</b>를 누르면 홈 화면에 나의 우주가 생겨요.</li>
        </ol>
      ) : (
        <p className="sub" style={{ margin: 0 }}>크롬 오른쪽 위 메뉴(⋮)에서 <b>&apos;홈 화면에 추가&apos;</b> 또는 <b>&apos;앱 설치&apos;</b>를 눌러요.</p>
      )}
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
