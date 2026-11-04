// 일기 먼저(2026-11-05 동규 A안), 가짜 데이터 모드: 처음 온 사람(?intro · 동의 전)은 동의 뒤 바로 이야기 화면 →
// 일기 3편째 저장 화면에서 되고 싶은 모습을 한 번 권함('지금 할게요' → 인터뷰 · '나중에' → 다시 안 권함) → 설정에서는 언제든 열기.
// 캡처는 docs/images/v8/<기기>-diaryfirst-NN-이름.png. 모두 지어낸 글.
import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { nav } from "./menu";

const OUT = path.resolve(__dirname, "../../../docs/images/v8");

// 직접 쓰기로 한 편 저장 → 저장 화면(확인 카드는 '다음에 할게요'로 넘김). n = 저장 뒤 일기 수(가짜 /me)
async function save(page: Page, n: number) {
  await nav(page, "직접 쓰기");
  await page.evaluate((x) => { (window as unknown as { __entries: number }).__entries = x; }, n);
  await page.getByLabel(/마음껏 적어/).fill(`오늘은 동네 도서관에서 책을 ${n}권 빌렸다. 돌아오는 길에 바람이 시원했다.`);
  await page.getByRole("button", { name: "우주에 띄우기" }).click();
  const after = page.getByTestId("after-save");
  await expect(after.getByTestId("saved-message")).toBeVisible({ timeout: 30_000 });
  const skip = after.getByRole("button", { name: "다음에 할게요" });
  if (await skip.isVisible()) await skip.click();
  return after;
}
// 권유가 안 뜨는지: 저장 화면이 /me 를 읽을 틈(가짜 0.1초)을 준 뒤 본다
async function noAsk(page: Page) {
  await page.waitForTimeout(1_000);
  await expect(page.getByTestId("aspiration-ask")).toHaveCount(0);
}

test("처음 온 사람: 동의 → 바로 이야기 → 3편째 저장 뒤 권유 → 설정에서 언제든", async ({ page }, info) => {
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${info.project.name}-diaryfirst-${name}.png` });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {   // 첫 방문 한 번만 동의 전
    if (!sessionStorage.getItem("fresh")) { localStorage.setItem("mock-consent", "none"); sessionStorage.setItem("fresh", "1"); }
  });

  await test.step("동의하면 되고 싶은 모습 인터뷰가 아니라 이야기(첫 대화)", async () => {
    await page.goto("/?intro");
    await expect(page).toHaveURL(/\/consent$/);
    await page.getByLabel(/이용약관.*개인정보 수집/).check();
    await page.getByLabel(/민감정보/).check();
    await page.getByRole("button", { name: "만 14세 이상이에요" }).click();
    await page.getByRole("button", { name: "동의하고 시작하기" }).click();
    await expect(page.getByRole("heading", { name: "이야기하기", level: 1 })).toBeAttached();
    await expect(page.getByRole("region", { name: "대화" })).toContainText("오늘 하루는 어땠어요?");
    await page.waitForTimeout(1_000);   // 예전엔 여기서 /aspiration?interview=1 로 옮겨 갔다
    expect(new URL(page.url()).pathname).toBe("/");
    await shot("01-start");
  });

  await test.step("2편째 저장: 아직 권하지 않음", async () => {
    await save(page, 2);
    await noAsk(page);
  });

  await test.step("3편째 저장: 되고 싶은 모습을 한 번 권함 → 지금 할게요 = 인터뷰", async () => {
    const after = await save(page, 3);
    const ask = after.getByTestId("aspiration-ask");
    await expect(ask).toContainText("되고 싶은 모습을 한번 같이 적어 보면");
    await ask.scrollIntoViewIfNeeded();
    await shot("02-ask");
    await ask.getByRole("link", { name: "지금 할게요" }).click();
    await expect(page).toHaveURL(/\/aspiration\?interview=1$/);
    const talk = page.getByRole("region", { name: "되고 싶은 모습 인터뷰" });
    await expect(talk).toContainText("다섯 가지만 천천히 물어볼게요");
    await expect(talk).not.toContainText("일기를 시작하기 전에");
    await talk.getByRole("button", { name: "나중에 할래요" }).click();
    await expect(page.getByRole("status")).toContainText("지금은 묻지 않을게요");
  });

  await test.step("나중에 뒤로는 다시 권하지 않음 · 설정에서는 언제든 열기", async () => {
    await save(page, 4);
    await noAsk(page);
    await page.getByRole("link", { name: "설정", exact: true }).click();
    await page.getByRole("group", { name: "설정 묶음" }).getByRole("button", { name: "말 걸기", exact: true }).click();
    const open = page.getByRole("link", { name: "되고 싶은 모습 열기" });
    await open.scrollIntoViewIfNeeded();
    await shot("03-settings");
    await open.click();
    await expect(page.getByRole("button", { name: "되고 싶은 모습 적어 보기" })).toBeVisible();
    await shot("03b-aspiration");
  });
  expect(errors).toEqual([]);
});

test("저장 화면의 '나중에' · 이미 정한 사람에겐 안 권함", async ({ page }) => {
  await test.step("되고 싶은 모습을 정한 사람(가짜 데이터 기본)은 3편째에도 안 권함", async () => {
    await page.goto("/");
    await save(page, 3);
    await noAsk(page);
  });
  await test.step("처음 사람: 3편째 권유에서 나중에 → 다음 저장부터 안 권함", async () => {
    await page.goto("/?intro");
    const ask = (await save(page, 3)).getByTestId("aspiration-ask");
    await ask.getByRole("button", { name: "나중에" }).click();
    await expect(ask).toContainText("지금은 묻지 않을게요");
    await save(page, 5);
    await noAsk(page);
  });
});
