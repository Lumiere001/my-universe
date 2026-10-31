// 화면 옮기기(PRD v9 휴대폰 틀, components/Shell.tsx): 탭 넷(이야기 · 일기장 · 우주 · 흐름)은 아래 탭 막대를 누르고,
// 탭 밖 화면은 앱 안에서 들어가는 자리(Q15)를 눌러 간다 — 주소로 바로 열면 가짜 데이터(메모리)가 새로 시작돼 앞 단계가 사라진다. 옛 메뉴 이름도 받는다.
import { type Page } from "@playwright/test";

const TAB: Record<string, string> = { 이야기: "이야기", 이야기하기: "이야기", 일기장: "일기장", "지난 기록": "일기장", 우주: "우주", 흐름: "흐름" };
const HREF: Record<string, string> = { 이야기: "/", 일기장: "/history", 우주: "/universe", 흐름: "/insight",
  "직접 쓰기": "/write", 사람: "/people", "되고 싶은 모습": "/aspiration", 설정: "/settings" };

export const tabs = (page: Page) => page.getByRole("navigation", { name: "탭", exact: true });
const tab = (page: Page, name: string) => tabs(page).getByRole("link", { name, exact: true }).click();

export async function nav(page: Page, name: string) {
  const t = TAB[name];
  if (t) await tab(page, t);
  else if (name === "직접 쓰기") { await tab(page, "이야기"); await page.getByRole("link", { name: "직접 쓰기" }).click(); }
  else if (name === "설정") await page.getByRole("link", { name: "설정", exact: true }).click();
  else if (name === "사람") { await tab(page, "우주"); await page.getByRole("link", { name: "사람 모두 보기" }).click(); }
  else if (name === "되고 싶은 모습") {
    await page.getByRole("link", { name: "설정", exact: true }).click();
    await page.getByRole("group", { name: "설정 묶음" }).getByRole("button", { name: "말 걸기", exact: true }).click();
    await page.getByRole("link", { name: "되고 싶은 모습 열기" }).click();
  } else throw new Error(`모르는 화면: ${name}`);
  const href = HREF[t ?? name];
  await page.waitForURL((u) => u.pathname === href);
}

// 저장 뒤(PRD v9 Q16 · Q18): 짧은 한마디 · 확인 카드 화면(after-save)에서 '일기 보기'로 결과 카드(원문 · 생각 · 이어진 생각)를 연다
export async function openResult(page: Page) {
  await page.getByTestId("after-save").getByRole("link", { name: "일기 보기" }).click({ timeout: 30_000 });
  await page.getByTestId("result").waitFor();
}
