// 메뉴 누르기: 휴대폰은 메뉴가 서랍 안에 있어 머리줄 단추로 먼저 열고, 화면이 바뀌고 서랍이 닫힐 때까지 기다린다(components/Shell.tsx)
import { expect, type Page } from "@playwright/test";

export const menu = (page: Page) => page.getByRole("navigation", { name: "화면", includeHidden: true });

export async function nav(page: Page, name: string) {
  const link = menu(page).getByRole("link", { name, exact: true, includeHidden: true });
  const drawer = !(await link.isVisible());
  if (drawer) await page.getByRole("button", { name: "메뉴 열기 · 닫기" }).click();
  const href = await link.getAttribute("href");
  await link.click();
  await page.waitForURL((u) => u.pathname === href);
  if (drawer) await expect(link).toBeHidden();
}
