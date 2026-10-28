// 설치형 웹앱 아이콘 · 공유 미리보기(OG) · 소개 화면 캡처를 만든다.
// 소개 캡처는 가짜 데이터 모드(가상 인물 하늘) 화면을 지금 디자인 그대로 찍는다(2026-10-28, 옵시디언 디자인). 먼저 그 서버를 띄운다:
//   NEXT_PUBLIC_MOCK=1 npx next dev -p 3211      (다른 터미널)
//   BASE=http://localhost:3211 node scripts/make-images.mjs
// 아이콘은 public/icons/icon.svg 하나에서 그린다. 디자인 · 테마 색 · 아이콘 그림을 바꾸면 다시 돌려 커밋한다(Playwright 의 chromium 만 씀, 외부 호출 없음).
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const WEB = path.resolve(import.meta.dirname, "..");
const BASE = (process.env.BASE || "http://localhost:3211").replace(/\/$/, "");
const PUB = (p) => path.join(WEB, "public", p);
const uri = (f, type) => `data:${type};base64,${fs.readFileSync(f).toString("base64")}`;
const svg = uri(PUB("icons/icon.svg"), "image/svg+xml");
const HIDE = "nextjs-portal { display: none !important; }";   // 개발 서버의 Next.js 표시
const JPG = { type: "jpeg", quality: 82, style: HIDE };

const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const page = await browser.newPage();
const draw = async (html, w, h, out, opts = {}) => {
  await page.setViewportSize({ width: w, height: h });
  await page.setContent(`<body style="margin:0">${html}</body>`, { waitUntil: "load" });
  await page.screenshot({ path: PUB(out), ...opts });
  console.log("만듦:", out);
};

for (const [n, out] of [[192, "icons/icon-192.png"], [512, "icons/icon-512.png"], [180, "icons/apple-touch-icon.png"]])
  await draw(`<img src="${svg}" width="${n}" height="${n}" style="display:block">`, n, n, out);

// 앱 화면 캡처: PC(1440x900, 1배) · 휴대폰(390x844, 2배). 우주가 저절로 돌지 않게(같은 그림)
const app = async (mobile) => {
  const ctx = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 },
    deviceScaleFactor: mobile ? 2 : 1, isMobile: mobile, hasTouch: mobile, reducedMotion: "reduce", locale: "ko-KR" });
  return ctx.newPage();
};
const universe = async (p) => {
  await p.goto(`${BASE}/universe`);
  await p.locator(".uni canvas").waitFor();
  await p.waitForTimeout(1500);
};
const shot = async (p, out, clip) => { await p.screenshot({ path: PUB(out), clip, ...JPG }); console.log("만듦:", out, `${clip.width}x${clip.height}`); };

const pc = await app(false);
await universe(pc);
await shot(pc, "landing/universe.jpg", { x: 264, y: 49, width: 1176, height: 851 });   // 사이드바 · 머리줄 뺀 우주 칸

const phone = await app(true);
await universe(phone);
await shot(phone, "landing/universe-mobile.jpg", { x: 0, y: 49, width: 390, height: 624 });
await phone.goto(`${BASE}/write`);
const [head, ...body] = fs.readFileSync(PUB("samples/haneul-2026-10-03.txt"), "utf8").trim().split("\n");   // 예시 일기: 첫 줄은 제목
await phone.getByLabel("제목 (비워도 돼요)").fill(head);
await phone.getByLabel(/마음껏 적어/).fill(body.join("\n"));
await phone.getByRole("button", { name: /^흐림/ }).click();
await phone.evaluate(() => document.activeElement?.blur());
await phone.waitForTimeout(500);
const t = await phone.getByLabel("제목 (비워도 돼요)").boundingBox();   // 제목부터(위의 별지기 말풍선은 빼고), 페이지 좌표로 잘라 냄
await phone.screenshot({ path: PUB("landing/write.jpg"), fullPage: true, clip: { x: 0, y: Math.round(t.y - 12), width: 390, height: 668 },
  ...JPG, style: HIDE + " .top { position: static !important; } .tabbar { display: none !important; }" });
console.log("만듦: landing/write.jpg 390x668");
await phone.getByRole("button", { name: "우주에 띄우기" }).click();
const voice = phone.getByRole("region", { name: "별지기 한마디" });
await voice.waitFor({ timeout: 20_000 });
await phone.waitForTimeout(500);
const b = await voice.boundingBox();
await shot(phone, "landing/message.jpg", { x: 0, y: Math.round(b.y - 12), width: 390, height: Math.round(b.height + 24) });

// 공유 미리보기 1200x630: 우주 캡처 위에 이름 · 한 줄(바탕 · 글자색은 globals.css --bg · --text · --muted)
const uni = uri(PUB("landing/universe.jpg"), "image/jpeg");
await draw(`<div style="width:1200px;height:630px;position:relative;overflow:hidden;background:#1e1e1e;font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif;color:#dadada">
  <img src="${uni}" style="position:absolute;right:-80px;top:-50px;width:1000px">
  <div style="position:absolute;inset:0;background:linear-gradient(90deg,#1e1e1e 34%,rgba(30,30,30,.6) 62%,rgba(30,30,30,0))"></div>
  <div style="position:absolute;left:72px;top:150px;width:560px">
    <img src="${svg}" width="112" height="112" style="border-radius:26px;display:block">
    <div style="font-size:76px;font-weight:800;margin:28px 0 14px;letter-spacing:-1px">나의 우주</div>
    <div style="font-size:31px;line-height:1.5;color:#b3b3b3">일기를 쓰면 생각이 별이 되고,<br>별지기가 지난 기록을 기억해 말을 걸어요</div>
  </div></div>`, 1200, 630, "og.jpg", { type: "jpeg", quality: 85 });

await browser.close();
