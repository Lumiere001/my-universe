// 받기 화면(부가티식 검은 바탕, 2026-11-02 동규)과 홈 화면 앱 첫 실행 카드뉴스. 가짜 데이터 모드는 ?signedout 이면 로그아웃 화면, ?cards 면 카드뉴스부터.
// 캡처는 docs/images/v9/<기기>-landing-NN-이름.png
import { expect, test } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/images/v9");

test("받기 화면: 우주 사진 · 하는 일 셋 · 약속 셋 · 받는 법", async ({ page }, info) => {
  // 맨 위 칸이 화면 높이(100svh)라 전체 길이 캡처는 칸이 같이 늘어나 실패 → 화면 크기로만 찍는다
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${info.project.name}-landing-${name}.png` });
  await page.goto("/?signedout");
  await expect(page.getByRole("heading", { name: "나의 우주", level: 1 })).toBeVisible();
  await expect(page.locator(".lux-hero img")).toHaveJSProperty("complete", true);
  expect(await page.locator(".lux-hero img").evaluate((i: HTMLImageElement) => i.naturalWidth)).toBeGreaterThan(0);
  // 굵은 글자 없음 · 버튼은 투명한 알약
  const btn = page.locator(".lux-hero-cta").getByRole("link", { name: "앱 받기" });
  expect(await btn.evaluate((b) => { const s = getComputedStyle(b); return [s.backgroundColor, s.fontWeight]; })).toEqual(["rgba(0, 0, 0, 0)", "400"]);
  await shot("01-hero");
  await expect(page.locator(".lux-model")).toHaveCount(3);
  await page.locator(".lux-model").first().scrollIntoViewIfNeeded();
  await shot("02-model");
  await page.locator(".lux-specs").scrollIntoViewIfNeeded();
  await shot("03-specs");
  await expect(page.locator(".lux-specs dt")).toHaveText(["10편", "AES-GCM", "가명"]);
  await btn.click();
  await expect(page.getByRole("heading", { name: "지금, 홈 화면에" })).toBeInViewport();
  // 시험 브라우저는 아이폰 · 안드로이드가 아니라 컴퓨터처럼: 휴대폰으로 열 QR 과 주소
  await expect(page.locator("#get")).toContainText("휴대폰 카메라로 비추면");
  await expect(page.getByRole("img", { name: "나의 우주 주소 QR 코드" })).toBeVisible();
  await shot("04-get");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);   // 옆으로 넘치지 않음
});

test("카드뉴스: 다섯 장을 넘기고 시작하기 → 시작 화면, 본 기기는 기억", async ({ page }, info) => {
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${info.project.name}-landing-${name}.png` });
  await page.goto("/?signedout&cards");
  const dialog = page.getByRole("dialog", { name: "나의 우주 소개" });
  await expect(dialog.getByRole("heading", { name: "반가워요, 나는 별지기예요" })).toBeVisible();
  await shot("05-cards-1");
  for (const title of ["오늘 하루를 말해 주세요", "내 말 그대로 일기 한 편", "생각이 별이 돼요", "내 일기는 나만 봐요"]) {
    await dialog.getByRole("button", { name: "다음" }).click();
    await expect(dialog.getByRole("heading", { name: title })).toBeInViewport();
  }
  await expect(dialog.locator(".cn-dots i").last()).toHaveAttribute("data-on", "true");   // 넘김이 끝난 뒤 찍기
  await shot("06-cards-5");
  await dialog.getByRole("button", { name: "시작하기" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("heading", { name: "나의 우주", level: 1 })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("cards-seen"))).toBe("1");
});
