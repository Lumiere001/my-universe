// 설치형 웹앱 아이콘 · 공유 미리보기(OG) · 소개 화면 캡처를 만든다.
// 받기 화면 캡처는 가짜 데이터 모드(가상 인물 하늘) 화면을 지금 디자인 그대로 찍는다(2026-11-02, 휴대폰 전용 · 손글씨 일기장).
// 받기 화면 맨 위 사진(hero)은 흑백 '먹' 테마 우주를 글자 · 버튼 없이(부가티식 검은 바탕). 먼저 그 서버를 띄운다:
//   NEXT_PUBLIC_MOCK=1 npx next dev -p 3211      (다른 터미널. 가짜 데이터로 빌드해 둔 것이 있으면 npx next start -p 3211)
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

const phone = await app(true);
await universe(phone);
await shot(phone, "landing/universe-mobile.jpg", { x: 0, y: 49, width: 390, height: 624 });
// 이야기 화면(카드뉴스 · 받기 화면): 첫 말에 한 번 답한 모습
await phone.goto(`${BASE}/`);
await phone.getByLabel("별지기에게 답하기").fill("오늘 친구 생일이라 오랜만에 먼저 문자를 보냈어. 답장이 바로 와서 기분이 좋았어.");
await phone.getByLabel("별지기에게 답하기").press("Enter");
await phone.locator(".bubble:not(.me)").nth(1).waitFor({ timeout: 20_000 });
await phone.evaluate(() => document.activeElement?.blur());
await phone.waitForTimeout(500);
await shot(phone, "landing/talk.jpg", { x: 0, y: 49, width: 390, height: 488 });   // 말풍선 셋까지(아래 빈 곳 뺌)

// 받기 화면 맨 위 사진: 설정에서 '먹' 테마를 고르고(가짜 데이터는 메모리라 탭을 눌러 옮김) 글자 · 버튼 없이
const BARE = { ...JPG, style: HIDE + " .lab, .top, .tabbar, main.uni-page button, main.uni-page a, main.uni-page p { visibility: hidden !important; }" };
for (const [mobile, out, clip] of [[false, "landing/hero.jpg", { x: 0, y: 49, width: 1440, height: 787 }],
  [true, "landing/hero-mobile.jpg", { x: 0, y: 49, width: 390, height: 731 }]]) {
  const p = await app(mobile);
  await p.goto(`${BASE}/settings`);
  await p.getByRole("group", { name: "설정 묶음" }).getByRole("button", { name: "우주와 화면", exact: true }).click();
  await p.getByRole("group", { name: "우주 테마" }).getByRole("button", { name: "먹" }).click();
  await p.getByRole("navigation", { name: "탭", exact: true }).getByRole("link", { name: "우주", exact: true }).click();
  await p.locator(".uni canvas").waitFor();
  await p.waitForTimeout(1500);
  await p.screenshot({ path: PUB(out), clip, ...BARE });
  console.log("만듦:", out, `${clip.width}x${clip.height}`);
}

await phone.goto(`${BASE}/write`);
const [head, ...body] = fs.readFileSync(PUB("samples/haneul-2026-10-03.txt"), "utf8").trim().split("\n");   // 예시 일기: 첫 줄은 제목
await phone.getByLabel("제목 (비워도 돼요)").fill(head);
await phone.getByLabel(/마음껏 적어/).fill(body.join("\n"));
await phone.getByRole("button", { name: /^구름 조금/ }).click();   // 받기 화면에 보이는 날씨는 잔잔한 쪽
await phone.evaluate(() => document.activeElement?.blur());
await phone.waitForTimeout(500);
const t = await phone.locator(".paper").boundingBox();   // 종이 한 장부터(위의 별지기의 추천은 빼고), 페이지 좌표로 잘라 냄
await phone.screenshot({ path: PUB("landing/write.jpg"), fullPage: true, clip: { x: 0, y: Math.round(t.y - 12), width: 390, height: 668 },
  ...JPG, style: HIDE + " .top { position: static !important; } .tabbar { display: none !important; }" });
console.log("만듦: landing/write.jpg 390x668");

// 공유 미리보기 1200x630: 받기 화면 맨 위와 같은 모습(검은 바탕 · 먹 우주 · 흰 글자 · 넓은 자간, 굵은 글자 없음)
const hero = uri(PUB("landing/hero.jpg"), "image/jpeg");
await draw(`<div style="width:1200px;height:630px;position:relative;overflow:hidden;background:#000;color:#fff;text-align:center;font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif">
  <img src="${hero}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.55">
  <div style="position:relative;margin-top:70px;font:400 15px/1 Menlo,monospace;letter-spacing:6px">MY UNIVERSE</div>
  <div style="position:relative;margin:150px -.16em 0 0;font-size:104px;font-weight:400;letter-spacing:.16em;line-height:1.1">나의 우주</div>
  <div style="position:relative;margin-top:26px;font-size:30px;color:#e6e6e6">말하듯 쓰는 일기, 생각이 우주가 돼요</div>
</div>`, 1200, 630, "og.jpg", { type: "jpeg", quality: 85 });

await browser.close();
