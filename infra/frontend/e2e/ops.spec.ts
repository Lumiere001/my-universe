// 운영 화면(WS22): 숫자 · 코드만 보이고, 피드백 원문은 누를 때만(동의한 사용자, 가명), 피드백 정리 결과가 보인다.
// 가짜 데이터 모드(lib/mock-ops.ts). 캡처는 docs/images/v8/<기기>-ops-NN-이름.png
import { expect, test } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/images/v8");

test("운영 화면", async ({ page }, info) => {
  const dev = info.project.name;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${dev}-ops-${name}.png`, fullPage: true, scale: "css", style: ".top { position: static; }" });   // 긴 휴대폰 화면은 2배로는 못 찍어 CSS 크기로

  await page.goto("/ops");
  await expect(page.getByRole("heading", { level: 1, name: "운영" })).toBeVisible();
  await expect(page.getByRole("region", { name: "추정 비용" })).toContainText("예산 $50");
  await expect(page.getByRole("region", { name: "만족 · 지향" })).toContainText("가까워졌다는 느낌");
  const me = page.getByRole("region", { name: "사람마다 · 개인 지표" });   // 개인 고리: 운영은 분포만
  await expect(me).toContainText("75%");
  await expect(me).toContainText("9명 · 자기 기준보다 나빠진 사람 1명");
  await expect(page.getByRole("table", { name: "피드백" })).toHaveCount(0);       // 원문은 누르기 전엔 없음
  await expect(page.getByRole("navigation", { name: "메뉴", exact: true, includeHidden: true }).getByRole("link", { name: "운영", includeHidden: true })).toHaveCount(0);   // 메뉴에 없음
  // 휴대폰에서도 가로로 넘치지 않는다(표는 자기 칸 안에서만 밀림)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  await shot("01-summary");

  await page.getByRole("button", { name: "최근 30일 열어 보기" }).click();
  await expect(page.getByRole("table", { name: "피드백" })).toContainText("사용자 1");
  await expect(page.getByRole("table", { name: "공통 틀 후보" })).toContainText("커리어 → 인간관계");   // ⑤: 여러 사람의 같은 고침
  await page.getByRole("button", { name: /피드백 정리/ }).click();
  await expect(page.getByLabel("피드백 정리 결과")).toContainText("설교 같음");
  await page.getByLabel("피드백 정리 결과").scrollIntoViewIfNeeded();
  await shot("02-feedback");
  expect(errors).toEqual([]);
});
