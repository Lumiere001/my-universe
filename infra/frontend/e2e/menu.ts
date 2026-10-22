// 메뉴 누르기: 휴대폰은 메뉴가 서랍 안에 있어 머리줄 단추로 먼저 연다(components/Shell.tsx)
import type { Page } from "@playwright/test";

export async function nav(page: Page, name: string) {
  const menu = page.getByRole("navigation", { name: "화면" });
  if (!(await menu.isVisible())) await page.getByRole("button", { name: "메뉴 열기 · 닫기" }).click();
  await menu.getByRole("link", { name, exact: true }).click();
}
