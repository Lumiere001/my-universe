"use client";
// 홈 화면에 앱으로 받는 법(설치형 웹앱 = 우리 전용 앱). 받기 화면(Landing, bare) · 설정 · 알림 켜기에서 보인다.
// 안드로이드 · PC 크롬: beforeinstallprompt 를 받아 '앱 설치' 버튼. 아이폰 · 아이패드 사파리: 공유 → 홈 화면에 추가 그림 안내.
// 이미 설치한 앱으로 열었으면(display-mode: standalone) 아무것도 보이지 않는다.
// 카톡 · 인스타그램처럼 앱 안의 브라우저로 열면 홈 화면에 추가가 안 돼서(2026-11-03, 카톡으로 링크를 받는 일이 많음) 사파리 · 크롬으로 여는 법을 먼저.
import { useEffect, useState } from "react";

type Prompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
type Mode = "none" | "prompt" | "ios" | "android" | "inapp";
export type Platform = "installed" | "ios" | "android" | "inapp" | "other";
// 앱 안의 브라우저(이름은 안내 문장에 씀). 안드로이드의 '; wv)' 는 이름 모를 앱 안 브라우저
const IN_APP: [RegExp, string][] = [[/KAKAOTALK/i, "카카오톡"], [/Instagram/, "인스타그램"], [/FBAN|FBAV/, "페이스북"], [/\bLine\//, "라인"],
  [/NAVER\(inapp/, "네이버 앱"], [/DaumApps/, "다음 앱"], [/; wv\)/, "앱"]];
export const inAppName = () => IN_APP.find(([re]) => re.test(navigator.userAgent))?.[1] ?? null;
const ios = () => /iPhone|iPad|iPod/.test(navigator.userAgent) || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);

// 지금 어디서 열었나(브라우저 밖에서만 부른다)
export function platform(): Platform {
  const nav = navigator as Navigator & { standalone?: boolean };
  if (matchMedia("(display-mode: standalone)").matches || nav.standalone) return "installed";
  if (inAppName()) return "inapp";
  if (ios()) return "ios";
  return /Android/.test(nav.userAgent) ? "android" : "other";
}

export default function InstallGuide({ bare }: { bare?: boolean }) {
  const [mode, setMode] = useState<Mode>("none");
  const [ev, setEv] = useState<Prompt | null>(null);

  useEffect(() => {
    const p = platform();
    if (p === "installed") return;
    if (p === "ios" || p === "android" || p === "inapp") setMode(p);
    if (p === "inapp") return;   // 앱 안 브라우저는 설치 창이 오지 않는다
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
    : mode === "inapp" ? <InApp />
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

// 앱 안 브라우저: 사파리(아이폰) · 크롬(안드로이드)으로 열기. 카톡은 바깥 브라우저로 여는 주소가 있고, 안드로이드는 크롬을 바로 부를 수 있다.
// 그 밖(아이폰 인스타그램 등)은 오른쪽 위 메뉴로 여는 법 + 주소 복사
function InApp() {
  const [copied, setCopied] = useState(false);
  const name = inAppName(), here = location.href;
  const [browser, ro] = ios() ? ["Safari", "로"] : ["Chrome", "으로"];   // 영어 이름 + 받침 맞춘 조사(2026-11-03 동규 「크롬로 → Chrome으로」)
  const open = /KAKAOTALK/i.test(navigator.userAgent) ? `kakaotalk://web/openExternal?url=${encodeURIComponent(here)}`
    : !ios() ? `intent://${location.host}${location.pathname}${location.search}#Intent;scheme=https;package=com.android.chrome;end` : null;
  const copy = () => navigator.clipboard?.writeText(here).then(() => setCopied(true), () => setCopied(false));
  return (
    <div className="stack">
      <p style={{ margin: 0 }}>{name} 안에서는 홈 화면에 둘 수 없어요. <b>{browser}</b>{ro} 열어 주세요.</p>
      {open ? <a className="primary btn" href={open}>{browser}{ro} 접속하기</a>
        : <p className="sub" style={{ margin: 0 }}>오른쪽 위(또는 아래) 메뉴 <b>⋯</b>에서 <b>{browser}{ro} 열기</b>(외부 브라우저로 열기)를 눌러요.</p>}
      <button type="button" className="link inline" onClick={copy}>{copied ? "주소를 복사했어요. " + browser + " 주소창에 붙여 넣어요." : "주소 복사하기"}</button>
    </div>
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
