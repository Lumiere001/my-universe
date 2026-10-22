// 이야기하기(WS19) · 요약 확인(WS20), 가짜 데이터 모드: 별지기가 먼저 물음(다짐 안부) → 세 턴 → 지금까지 정리 → 끝낼 말에 정리 제안
// → 대화 마치고 정리하기 → 요약 확인(요약 고치기 · 종류 고치기 · 생각 빼기) → 저장 뒤 한마디는 대화 안 말풍선 → 위기 말은 위로 + 안부 한 줄
// → 행성 카드에서 '이 이야기 이어 하기'. 캡처는 docs/images/v8/<기기>-talk-NN-이름.png. 모두 가상 인물 하늘의 글 · 지어낸 글.
import { expect, test } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/images/v8");
const HOTLINE = /(?<!\d)(?:109|112|119)(?!\d)|마들랜|상담 ?전화/;

test("이야기하기 → 요약 확인", async ({ page }, info) => {
  const dev = info.project.name;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const shot = (name: string, full = false) => page.screenshot({ path: `${OUT}/${dev}-talk-${name}.png`, fullPage: full,
    style: full ? ".tabbar { visibility: hidden; }" : undefined });
  const talk = page.getByRole("region", { name: "대화" });
  const say = async (t: string, n: number) => {
    await page.getByLabel("별지기에게 답하기").fill(t);
    await page.getByRole("button", { name: "보내기" }).click();
    await expect(talk.locator(".bubble.me")).toHaveCount(n);
    await expect(page.getByRole("button", { name: "보내기" })).toBeDisabled();   // 칸이 비면 보내기는 꺼짐(답이 붙음)
  };

  await test.step("별지기가 먼저 묻는다(다짐 안부)", async () => {
    await page.goto("/");   // 로그인 뒤 첫 화면 = 이야기하기(2026-10-14 결정), 직접 쓰기는 /write
    await expect(page.getByRole("heading", { name: "이야기하기", level: 1 })).toBeVisible();
    const menu = page.getByRole("navigation", { name: "메뉴", exact: true, includeHidden: true });
    await expect(menu.getByRole("link", { name: "이야기하기", exact: true, includeHidden: true })).toHaveAttribute("aria-current", "page");
    await expect(menu.getByRole("link", { name: "직접 쓰기", exact: true, includeHidden: true })).toHaveAttribute("href", "/write");
    await expect(talk).toContainText("관심 있는 팀 세 곳을 직접 찾아보겠다.");
    await shot("01-start");
  });

  await test.step("세 턴 → 지금까지 정리 → 끝낼 말에 정리 제안", async () => {
    await say("오늘 드디어 팀 한 곳에 메일을 보냈어.", 1);
    await say("답장은 아직인데 보내고 나니 후련했어.", 2);
    await say("부모님께는 아직 말 못 했어.", 3);
    await page.getByText("지금까지 정리").click();
    await expect(page.locator("main details")).toContainText("메일을 보냈어");
    await say("오늘은 여기까지 할게", 4);
    await expect(talk).toContainText("대화 마치고 정리하기");
    await shot("02-chat", true);
  });

  await test.step("대화 마치고 정리하기 → 요약 확인에서 고쳐 저장", async () => {
    await page.getByRole("button", { name: "대화 마치고 정리하기" }).click();
    const card = page.getByTestId("confirm-card");
    await expect(card).toBeVisible();
    await card.getByRole("group", { name: "요약이 맞나요" }).getByRole("button", { name: "고칠래요" }).click();
    await card.getByLabel("요약 고치기").fill("팀 한 곳에 메일을 보냈고, 부모님께는 아직 말하지 못했다.");
    const groups = card.getByRole("group", { name: "이 생각이 맞나요" });
    await groups.nth(0).getByRole("button", { name: "맞아요" }).click();
    await groups.nth(1).getByRole("button", { name: "고칠래요" }).click();
    await card.locator("select").first().selectOption("해석");
    await groups.nth(3).getByRole("button", { name: "고칠래요" }).click();
    await card.getByLabel("이 생각 빼기").last().check();
    await expect(card.getByText("뺄 생각")).toBeVisible();
    await shot("03-confirm", true);
    await card.getByRole("button", { name: "확인하고 우주에 저장" }).click();
    await expect(page.getByTestId("saved-message")).toBeVisible();
    await expect(page.getByRole("region", { name: "저장했어요" })).toBeVisible();
    await shot("04-saved");
  });

  await test.step("위기 말 → 위로 + 안부 한 줄(질문 · 단체 안내 없음)", async () => {
    await page.getByRole("button", { name: "새 대화 시작" }).last().click();
    await say("요즘 너무 지쳐서 사라지고 싶다는 생각이 들어.", 1);
    const reply = talk.locator(".voice").last();
    await expect(reply.getByTestId("check-in")).toBeVisible();
    await expect(reply).not.toContainText("?");
    await expect(talk).not.toContainText(HOTLINE);
    await shot("05-crisis");
  });

  await test.step("행성 카드 → 이 이야기 이어 하기", async () => {
    await page.goto("/universe/e02");
    await page.getByRole("link", { name: "이 이야기 이어 하기" }).click();
    await expect(talk).toContainText("3/14 진로 상담");
    await expect(talk).toContainText("이어 해 볼까요");
  });

  await test.step("좁은 휴대폰(360px)에서도 아래 막대 7개가 가로로 넘치지 않음", async () => {
    await page.setViewportSize({ width: 360, height: 780 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
    if (dev === "mobile") await shot("06-nav-360");
  });
  expect(errors).toEqual([]);
});
