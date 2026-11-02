// 자라는 해(2026-11-02 동규, 기준 10편): 저장 뒤 '새 해가 태어났어요' 카드 → 우주에서 그 해를 보여 줌.
// 가짜 데이터는 '취미'가 든 글이면 해 「여가」가 태어난다. 시험은 움직임 줄이기라 커지는 모습은 건너뛰고 해만 확인.
import { expect, test } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/images/v9");

test("새 해가 태어나면 저장 뒤 카드 → 우주에서 그 해", async ({ page }, info) => {
  await page.goto("/write");
  await page.getByLabel(/마음껏 적어/).fill("주말에 새 취미로 수채화를 시작했다. 붓질 몇 번에 마음이 차분해졌다.");
  await page.getByRole("button", { name: "우주에 띄우기" }).click();
  const card = page.getByText("새 해가 태어났어요");
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("after-save")).toContainText("여가");
  await page.screenshot({ path: `${OUT}/${info.project.name}-sun-01-card.png` });
  await page.getByRole("link", { name: "태어나는 모습 보기" }).click();
  await page.waitForURL((u) => u.pathname === "/universe" && u.searchParams.get("born") === "여가");
  await expect(page.locator(".born-note")).toContainText("여가");
  await expect(page.locator(".uni .lab.sun", { hasText: "여가" })).toBeAttached();
  await page.screenshot({ path: `${OUT}/${info.project.name}-sun-02-universe.png` });
});
