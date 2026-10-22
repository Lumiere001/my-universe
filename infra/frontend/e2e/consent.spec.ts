// 첫 로그인 동의(WS24): 동의하지 않으면 쓰기 · 기록 화면으로 못 가고, 만 14세 미만은 시작할 수 없다.
// 가짜 데이터 모드는 기본이 '이미 동의한 사용자'라 localStorage mock-consent=none 으로 동의 전 사용자를 만든다.
// 캡처는 docs/images/v8/<기기>-consent-NN-이름.png
import { expect, test } from "@playwright/test";
import { nav as menuNav } from "./menu";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/images/v8");
// 시험 단계(2026-10-08 동규): 동의 · 약관 · 방침 화면에도 단체 이름 · 전화번호가 나오지 않는다
const HOTLINE = /(?<!\d)(?:109|112|119)(?!\d)|마들랜|상담 ?전화/;

test("동의 전에는 쓰기 화면으로 못 감", async ({ page }, info) => {
  const dev = info.project.name;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // 첫 방문 한 번만 '동의 전'으로 만든다(동의 뒤 새로 고침에서는 그대로 둠)
  await page.addInitScript(() => {
    if (!sessionStorage.getItem("ws24")) { localStorage.setItem("mock-consent", "none"); sessionStorage.setItem("ws24", "1"); }
  });
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${dev}-consent-${name}.png`, fullPage: true, style: ".top { position: static; } .tabbar { visibility: hidden; }" });
  const start = page.getByRole("button", { name: "동의하고 시작하기" });

  await test.step("쓰기 화면 대신 동의 화면", async () => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/consent$/);
    await expect(page.getByRole("heading", { level: 1, name: "나의 우주를 쓰기 전에" })).toBeVisible();
    await expect(page.getByLabel(/마음껏 적어/)).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: "메뉴", exact: true, includeHidden: true })).toHaveCount(0);
    for (const where of ["/universe", "/history", "/people", "/aspiration"]) {
      await page.goto(where);
      await expect(page).toHaveURL(/\/consent$/);
    }
    await expect(page.getByRole("region", { name: "외부로 나가는 곳" })).toContainText("ElevenLabs");
    await expect(page.getByRole("region", { name: "외부로 나가는 곳" })).toContainText("국외 이전");
    await expect(start).toBeDisabled();
    await shot("01-gate");
  });

  await test.step("필수 하나만 · 14세 미만이면 시작 못 함", async () => {
    await page.getByLabel(/이용약관.*개인정보 수집/).check();
    await expect(start).toBeDisabled();
    await page.getByLabel(/민감정보/).check();
    await expect(start).toBeDisabled();
    await page.getByRole("button", { name: "만 14세 미만이에요" }).click();
    await expect(page.getByTestId("under-14")).toContainText("지금은 쓸 수 없어요");
    await expect(start).toBeDisabled();
    await shot("02-under-14");
  });

  await test.step("필수 셋에 동의하면 첫 화면(이야기하기)", async () => {
    await page.getByRole("button", { name: "만 14세 이상이에요" }).click();
    await expect(page.getByTestId("under-14")).toHaveCount(0);
    await expect(start).toBeEnabled();
    await start.click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "이야기하기", level: 1 })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "메뉴", exact: true, includeHidden: true })).toHaveCount(1);
  });

  await test.step("설정 → 동의 내용(선택 동의 바꾸기) · 이용약관 · 개인정보처리방침", async () => {
    await menuNav(page, "설정");
    await page.getByRole("link", { name: "동의 내용 보기 · 바꾸기" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "동의 내용" })).toBeVisible();
    await page.getByLabel(/운영자가 내가 남긴 피드백/).check();
    await page.getByRole("button", { name: "바꾼 내용 저장" }).click();
    await expect(page.getByRole("status")).toContainText("저장했어요");
    expect(await page.textContent("main")).not.toMatch(HOTLINE);
    await page.goto("/terms");
    await expect(page.getByRole("heading", { level: 1, name: "나의 우주 이용약관" })).toBeVisible();
    await expect(page.getByText("의료 · 심리 상담 서비스가 아니에요")).toBeVisible();
    await expect(page.getByTestId("contact-pending")).toBeVisible();   // NEXT_PUBLIC_CONTACT_EMAIL 이 비면 '준비 중'
    expect(await page.textContent("main")).not.toMatch(HOTLINE);
    await shot("03-terms");
    await page.goto("/privacy");
    const main = page.locator("main");
    for (const s of ["저장하지 않아요", "바로 버려요", "확인한 정리본만", "실명 그대로", "국외 이전", "선택 동의한 사람 것만", "만 14세 미만", "따로"]) {
      await expect(main).toContainText(s);
    }
    expect(await main.textContent()).not.toMatch(HOTLINE);
  });
  expect(errors).toEqual([]);
});
