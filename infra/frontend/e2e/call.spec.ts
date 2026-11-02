// 전화로 이야기하기(2026-11-03 동규 「헤이링처럼」 → A안 별이 태어나는 대화): 이야기 탭의 전화 단추 → 말 걸어 옴(내 우주 + 성운) → 받기 → 성운 · 자막 → 끊기 → 별 · 대본 → 일기로 정리하기 → 정리 확인.
// 가짜 데이터 모드의 연습 엔진(정해 둔 문장으로 주고받기). 캡처는 docs/images/v9/<기기>-call-NN-이름.png
import { expect, test } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/images/v9");

test("전화 옴 → 통화(원 · 자막) → 끊기 → 대본 → 일기로 정리하기", async ({ page }, info) => {
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${info.project.name}-call-${name}.png` });
  await page.goto("/");
  await page.getByRole("link", { name: "목소리로 이야기하기" }).click();
  await page.waitForURL("**/call");
  const call = page.getByRole("dialog", { name: /와 대화$/ });
  await expect(call.getByRole("heading", { name: "별지기" })).toBeVisible();
  await expect(call.getByRole("link", { name: "나중에" })).toHaveAttribute("href", "/");
  await expect(call.locator("canvas.call-cosmos"), "배경은 내 우주(행성 화면)").toBeVisible();
  await expect(call.locator("canvas.call-nebula"), "가운데 성운(별이 태어나는 대화)").toBeVisible();
  await shot("01-ring");

  await call.getByRole("button", { name: "받기" }).click();
  await expect(call.getByRole("status")).toHaveText("별지기가 말하고 있어요");
  await expect(call.locator(".call-caption")).toContainText("오늘 하루는 어땠어요?");
  await expect(call.locator(".call-space")).toHaveAttribute("data-mode", "speaking");
  await shot("02-speaking");
  await expect(call.getByRole("status")).toHaveText(/듣고 있어요/, { timeout: 10_000 });
  await expect(call.locator(".call-space")).toHaveAttribute("data-mode", "listening");
  await shot("03-listening");
  await expect(call.locator(".call-caption")).toContainText("메일을 보냈어", { timeout: 15_000 });
  await expect(call.getByRole("status")).toHaveText("별지기가 말하고 있어요", { timeout: 15_000 });   // 내 말 → 별지기 답

  await call.getByRole("button", { name: "마이크 끄기" }).click();
  await expect(call.getByRole("button", { name: "마이크 켜기" })).toHaveAttribute("aria-pressed", "true");
  await call.getByRole("button", { name: "끊기" }).click();
  await expect(call.getByRole("heading", { name: "대화가 끝났어요" })).toBeVisible();
  await expect(call.getByText(/오늘 이야기로 별 하나가 생겼어요/)).toBeVisible();
  const script = call.getByRole("list", { name: "대화 대본" });
  await expect(script.locator("li.keeper").first()).toContainText("오늘 하루는 어땠어요?");
  await expect(script.locator("li.me").first()).toContainText("메일을 보냈어");
  await expect(script.locator("li.keeper")).toHaveCount(2);
  await shot("04-script");

  await call.getByRole("button", { name: "일기로 정리하기" }).click();
  await page.waitForURL((u) => u.pathname === "/" && !u.search);   // 바로 정리하고 주소의 ?finish 는 지움
  await expect(page.getByText("오늘 이야기를 이렇게 정리했어요")).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".paper")).toContainText("메일을 보냈어");   // 통화 속 내 말이 일기 원문으로
  await shot("05-confirm");
});
