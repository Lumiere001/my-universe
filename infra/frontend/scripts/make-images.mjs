// 설치형 웹앱 아이콘 · 공유 미리보기(OG) · 소개 화면 캡처를 만든다: node scripts/make-images.mjs
// 아이콘은 public/icons/icon.svg 하나에서 그린다. 캡처 원본은 docs/images/v8-real/(로컬 시험 계정 tester@ 의 하늘 데모 우주 — 가상 인물).
// 테마 색이나 아이콘 그림을 바꾸면 다시 돌려 커밋한다(Playwright 의 chromium 만 씀, 외부 호출 없음).
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const WEB = path.resolve(import.meta.dirname, "..");
const SHOTS = path.resolve(WEB, "../../docs/images/v8-real");
const PUB = (p) => path.join(WEB, "public", p);
const uri = (f, type) => `data:${type};base64,${fs.readFileSync(f).toString("base64")}`;
const svg = uri(PUB("icons/icon.svg"), "image/svg+xml");

const browser = await chromium.launch();
const page = await browser.newPage();
const draw = async (html, w, h, out, opts = {}) => {
  await page.setViewportSize({ width: w, height: h });
  await page.setContent(`<body style="margin:0">${html}</body>`, { waitUntil: "load" });
  await page.screenshot({ path: PUB(out), ...opts });
  console.log("만듦:", out);
};

for (const [n, out] of [[192, "icons/icon-192.png"], [512, "icons/icon-512.png"], [180, "icons/apple-touch-icon.png"]])
  await draw(`<img src="${svg}" width="${n}" height="${n}" style="display:block">`, n, n, out);

// 캡처에서 잘라 내기: [원본, x, y, 너비, 높이, 결과]
for (const [src, x, y, w, h, out] of [
  ["pc-02-universe.png", 97, 78, 1246, 748, "landing/universe.jpg"],
  ["mobile-07-write.png", 0, 52, 390, 668, "landing/write.jpg"],
  ["mobile-02-universe.png", 0, 52, 390, 624, "landing/universe-mobile.jpg"],
  ["mobile-10-result.png", 0, 48, 390, 316, "landing/message.jpg"],
]) {
  const img = uri(path.join(SHOTS, src), "image/png");
  await draw(`<img src="${img}" style="display:block">`, x + w, y + h, out, { type: "jpeg", quality: 82, clip: { x, y, width: w, height: h } });
}

// 공유 미리보기 1200x630: 우주 캡처 위에 이름 · 한 줄
const uni = uri(PUB("landing/universe.jpg"), "image/jpeg");
await draw(`<div style="width:1200px;height:630px;position:relative;overflow:hidden;background:#07102a;font-family:'Apple SD Gothic Neo','Noto Sans KR',sans-serif;color:#e8eefc">
  <img src="${uni}" style="position:absolute;right:-80px;top:-40px;width:1000px">
  <div style="position:absolute;inset:0;background:linear-gradient(90deg,#07102a 34%,rgba(7,16,42,.55) 62%,rgba(7,16,42,0))"></div>
  <div style="position:absolute;left:72px;top:150px;width:560px">
    <img src="${svg}" width="112" height="112" style="border-radius:26px;display:block">
    <div style="font-size:76px;font-weight:800;margin:28px 0 14px;letter-spacing:-1px">나의 우주</div>
    <div style="font-size:31px;line-height:1.5;color:#c9d4f2">일기를 쓰면 생각이 별이 되고,<br>별지기가 지난 기록을 기억해 말을 걸어요</div>
  </div></div>`, 1200, 630, "og.jpg", { type: "jpeg", quality: 85 });

await browser.close();
