// 핵심 흐름: 쓰기 → 진행 → 결과 카드 → 피드백 → 우주 → 행성 → 해 → 사람 고르기 → 되고 싶은 모습 → 팩폭 경고 → 위기 돌봄
// → 끊김 뒤 이어서 하기 → 사람 지우기 → 지난 기록. 캡처는 docs/images/v8/<기기>-NN-이름.png
import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/images/v8");
// 가상 인물 하늘의 10/3 일기(data/samples/하늘-2026-10-03.txt) + 지어낸 한 줄
const HANEUL = `10/3 토요일 일기
지난주에 관심 있는 팀 세 곳을 직접 찾아보기로 했는데, 결국 한 곳도 찾아보지 못했다. 바쁘다는 핑계로 또 미뤘다. 이런 내가 조금 실망스럽다.
그래도 요즘 생각은 조금 정리됐다. 예전에는 큰 회사에 들어가야만 인정받는다고 생각했는데, 이제는 어디서 일하든 내가 배우고 있다는 느낌이 더 중요하다는 걸 알겠다.
부모님께는 아직 말씀드리지 못했다. 다음 주에는 한 곳이라도 먼저 메일을 보내 보고 싶다.
저녁에 민수 형한테 연락할까 하다가 말았다.`;
const CRISIS = "요즘 너무 지쳐서 다 끝내고 싶다는 생각이 자꾸 든다.";

test("핵심 흐름", async ({ page }, info) => {
  const dev = info.project.name;
  const errors: string[] = [];
  page.on("pageerror", (e) => { errors.push(e.message); console.log("화면 오류:", e.stack); });
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  // 긴 화면 전체 캡처에서는 고정된 아래 막대가 가운데 찍히므로 그때만 감춘다
  const shot = (name: string, full = false) => page.screenshot({ path: `${OUT}/${dev}-${name}.png`, fullPage: full,
    style: full ? ".top .nav { visibility: hidden; }" : undefined });
  const nav = (name: string) => page.getByRole("navigation", { name: "화면" }).getByRole("link", { name, exact: true }).click();
  const tapAt = async (id: string) => {
    const { x, y } = await page.evaluate((i) => (window as unknown as { __uni: { xy: (i: string) => { x: number; y: number } } }).__uni.xy(i), id);
    if (info.project.use.hasTouch) await page.touchscreen.tap(x, y); else await page.mouse.click(x, y);
  };

  await test.step("쓰기: 글과 마음 날씨", async () => {
    await page.goto("/");
    await page.getByLabel(/마음껏 적어/).fill(HANEUL);
    await page.getByRole("button", { name: /^흐림/ }).click();
    await expect(page.getByRole("button", { name: /^흐림/ })).toHaveAttribute("aria-pressed", "true");
    await shot("01-write");
  });

  await test.step("진행 단계", async () => {
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    await expect(page.getByText("지난 생각을 찾는 중")).toBeVisible();
    await shot("02-progress");
  });

  await test.step("결과 카드", async () => {
    const r = page.getByTestId("result");
    await expect(r).toBeVisible({ timeout: 15_000 });
    await expect(r.getByRole("region", { name: "별지기 한마디" })).toContainText("다정하게");
    await expect(r.getByRole("region", { name: "생각 목록" })).toContainText("아쉬웠던 점"); // 온톨로지 보이는 이름
    await expect(r.getByText("스스로 쓴 변화: 예전에는 큰 회사")).toBeVisible();
    await expect(r.getByText("지난 생각 3개와 이어졌어요")).toBeVisible();
    await expect(r.getByText("북극성에 닿은 순간")).toBeVisible();
    await shot("03-result", true);
  });

  await test.step("피드백 누르기", async () => {
    await page.getByRole("group", { name: "한마디 피드백" }).getByRole("button", { name: "좋아요" }).click();
    await expect(page.getByRole("group", { name: "한마디 피드백" }).getByText("고마워요")).toBeVisible();
    await page.getByRole("group", { name: "이 연결이 맞나요" }).first().getByRole("button", { name: "맞아요" }).click();
    await page.getByRole("group", { name: "다짐 상태" }).getByRole("button", { name: "지켰어요" }).click();
    await expect(page.getByText("다짐 지켜짐")).toBeVisible();
    await page.getByRole("button", { name: "같은 사람" }).click();
    await expect(page.getByText("“같은 사람”로 기억할게요.")).toBeVisible();
    await page.getByRole("textbox", { name: "불편한 점 한 줄" }).fill("생각을 너무 잘게 나눈 것 같아요");
    await page.getByRole("button", { name: "보내기" }).click();
    await expect(page.getByText("불편한 점을 받았어요")).toBeVisible();
    await shot("04-feedback", true);
  });

  await test.step("3D 우주", async () => {
    await nav("우주");
    await expect(page.locator(".uni canvas")).toBeVisible();
    await expect(page.locator(".uni .lab.sun").first()).toBeVisible();
    await page.waitForTimeout(800);
    await shot("05-universe");
  });

  await test.step("행성 누르기 → 요약 카드", async () => {
    await tapAt("e11");
    const card = page.getByTestId("planet-card");
    await expect(card).toContainText("6/20 혼자와 함께");
    await expect(card).toContainText("혼자는 충전");
    await expect(card).toContainText("다른 영역"); // 영역 넘는 선은 눌렀을 때만
    await page.waitForTimeout(300);
    await shot("06-planet");
    await card.getByRole("button", { name: "닫기" }).click();
  });

  await test.step("해 누르기 → 그 태양계로", async () => {
    await tapAt("d1");
    await page.waitForTimeout(300);
    await expect(page.getByTestId("planet-card")).toHaveCount(0);
    await shot("07-sun");
  });

  await test.step("사람 고르기 → 그 사람이 나온 행성이 빛남", async () => {
    const minsu = page.getByRole("group", { name: "사람 고르기" }).getByRole("button", { name: /민수/ });
    await minsu.click();
    await expect(minsu).toHaveAttribute("aria-pressed", "true");
    await page.waitForTimeout(300);
    await shot("08-person");
  });

  await test.step("되고 싶은 모습 대화형 폼", async () => {
    await nav("되고 싶은 나");
    await page.getByRole("button", { name: "새로 적기" }).click();
    const answers = ["바쁘다는 말로 자꾸 미루는 사람", "어디서든 배우고, 한 약속은 지키는 사람", "피곤하면 다 내일로 미룬다", "피곤하면 오 분만 하고 자겠다"];
    for (const [i, a] of answers.entries()) {
      await page.locator("#asp").fill(a);
      if (i === 2) await shot("09-aspiration-form");
      await page.getByRole("button", { name: "다음" }).click();
    }
    await page.getByRole("button", { name: "성취" }).click();
    await page.getByRole("button", { name: "규범" }).click();
    await page.getByRole("button", { name: "북극성으로 띄우기" }).click();
    await expect(page.getByText("북극성으로 띄웠어요")).toBeVisible();
    await expect(page.getByRole("region", { name: "지금의 북극성" })).toContainText("어디서든 배우고, 한 약속은 지키는 사람");
    await page.getByText(/이력 보기/).click();
    await shot("10-aspiration-saved", true);
  });

  await test.step("설정: 팩폭은 경고 확인 뒤에만", async () => {
    await nav("설정");
    await page.getByRole("button", { name: /^담백하게/ }).click();
    await expect(page.getByText("미리보기")).toBeVisible();
    await page.getByRole("button", { name: /^팩폭/ }).click();
    const w = page.getByTestId("fact-bomb-warning");
    await expect(w).toContainText("거친 말이 나와요");
    await expect(w.locator("li")).toHaveCount(4);
    await expect(page.getByRole("button", { name: /^팩폭/ })).toHaveAttribute("aria-pressed", "false"); // 아직 안 골라짐
    await shot("11-fact-bomb-warning", true);
    await w.getByRole("button", { name: /팩폭으로 할게요/ }).click();
    await expect(page.getByRole("button", { name: /^팩폭/ })).toHaveAttribute("aria-pressed", "true");
  });

  await test.step("위기 글 → 돌봄 화면만", async () => {
    await nav("쓰기");
    await page.getByLabel(/마음껏 적어/).fill(CRISIS);
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    const care = page.getByTestId("care");
    await expect(care).toBeVisible({ timeout: 15_000 });
    await expect(care.getByRole("link", { name: /109/ })).toHaveAttribute("href", "tel:109");
    await expect(care).toContainText("마들랜");
    await expect(page.getByTestId("result")).toHaveCount(0);
    await expect(page.locator("main button")).toHaveCount(0); // 다른 버튼 없음
    await shot("12-care");
  });

  await test.step("끊김 → 이어서 하기", async () => {
    await nav("지난 기록");
    await nav("쓰기");
    await page.getByLabel(/마음껏 적어/).fill(HANEUL + "\n[끊김]");
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    const resume = page.getByRole("button", { name: "이어서 하기" });
    await expect(resume).toBeVisible({ timeout: 15_000 });
    await shot("13-resume");
    await resume.click();
    await expect(page.getByTestId("result")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("region", { name: "별지기 한마디" })).toContainText("팩폭"); // 바꾼 말투가 반영됨
  });

  await test.step("사람 지우기(이름을 관계 말로)", async () => {
    await nav("사람");
    await page.getByRole("button", { name: "지은 지우기" }).click();
    const dlg = page.getByRole("alertdialog", { name: "지은 지우기 확인" });
    await expect(dlg).toContainText("관계 말 “동생”");
    await expect(dlg).toContainText("문장 · 생각 · 이어진 선은 그대로");
    await shot("14-people-delete", true);
    await dlg.getByRole("button", { name: "지우기" }).click();
    await expect(page.getByText(/지은을\(를\) 지웠어요/)).toBeVisible();
  });

  await test.step("지난 기록", async () => {
    await nav("지난 기록");
    await expect(page.getByRole("button", { name: /10\/3 토요일 일기/ }).first()).toBeVisible();
    await shot("15-history");
    await page.getByRole("button", { name: /9\/20 토요일 일기/ }).click();
    await expect(page.getByTestId("result")).toBeVisible();
  });

  expect(errors, "화면 오류가 없어야 함").toEqual([]);
});
