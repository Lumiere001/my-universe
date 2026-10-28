// 핵심 흐름: 쓰기 → 진행 → 결과 카드 → 피드백 → 우주 → 행성 → 해 → 사람 고르기 → 되고 싶은 모습 → 팩폭 경고 → 개인정보처리방침 → 위기 글(평소 결과 + 안부 한 줄)
// → 끊김 뒤 이어서 하기 → 사람 지우기 → 지난 기록. 캡처는 docs/images/v8/<기기>-NN-이름.png
import { expect, test, type Page } from "@playwright/test";
import { nav as menuNav } from "./menu";
import path from "node:path";
import { josa, particle } from "../lib/josa";

const OUT = path.resolve(__dirname, "../../../docs/images/v8");
// 가상 인물 하늘의 10/3 일기(data/samples/하늘-2026-10-03.txt) + 지어낸 한 줄
const HANEUL = `10/3 토요일 일기
지난주에 관심 있는 팀 세 곳을 직접 찾아보기로 했는데, 결국 한 곳도 찾아보지 못했다. 바쁘다는 핑계로 또 미뤘다. 이런 내가 조금 실망스럽다.
그래도 요즘 생각은 조금 정리됐다. 예전에는 큰 회사에 들어가야만 인정받는다고 생각했는데, 이제는 어디서 일하든 내가 배우고 있다는 느낌이 더 중요하다는 걸 알겠다.
부모님께는 아직 말씀드리지 못했다. 다음 주에는 한 곳이라도 먼저 메일을 보내 보고 싶다.
저녁에 민수 형한테 연락할까 하다가 말았다.`;
const CRISIS = "요즘 너무 지쳐서 다 끝내고 싶다는 생각이 자꾸 든다.";
// 시험 단계(2026-10-08 동규): 위기 글이어도 화면에 단체 이름 · 전화번호가 나오지 않는다
const HOTLINE = /(?<!\d)(?:109|112|119)(?!\d)|마들랜|상담 ?전화/;

test("조사: 받침에 맞춰 하나만(을(를) 대신, 2026-10-28)", () => {
  expect([josa("엄마", "을/를"), josa("지은", "을/를"), josa("민수", "과/와"), josa("서윤", "과/와")]).toEqual(["엄마를", "지은을", "민수와", "서윤과"]);
  expect([particle("부모", "으로/로"), particle("동생", "으로/로"), particle("교실", "으로/로"), particle("형제자매", "이/가")]).toEqual(["로", "으로", "로", "가"]);
  expect([josa("그 사람", "은/는"), josa("Alex", "을/를")]).toEqual(["그 사람은", "Alex을(를)"]);   // 한글이 아니면 둘 다
});

test("핵심 흐름", async ({ page }, info) => {
  const dev = info.project.name;
  const errors: string[] = [];
  page.on("pageerror", (e) => { errors.push(e.message); console.log("화면 오류:", e.stack); });
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  // 긴 화면 전체 캡처에서는 고정된 아래 막대가 가운데 찍히므로 그때만 감춘다
  const shot = (name: string, full = false) => page.screenshot({ path: `${OUT}/${dev}-${name}.png`, fullPage: full,
    style: full ? ".tabbar { visibility: hidden; }" : undefined });
  const nav = (name: string) => menuNav(page, name);
  const tapAt = async (id: string) => {
    const { x, y } = await page.evaluate((i) => (window as unknown as { __uni: { xy: (i: string) => { x: number; y: number } } }).__uni.xy(i), id);
    if (info.project.use.hasTouch) await page.touchscreen.tap(x, y); else await page.mouse.click(x, y);
  };

  await test.step("쓰기: 글과 마음 날씨", async () => {
    await page.goto("/write");
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
    const parts = r.getByRole("group", { name: "나눠 보기" });   // 생각 · 이어진 생각 · 같은 주제 · 더 보기 중 하나만(한 화면에 가깝게)
    await expect(parts.getByRole("button", { name: "이어진 생각 3" })).toBeVisible();
    await expect(r.getByText("북극성에 닿은 순간")).toBeVisible();
    await expect(r.getByTestId("entry-day")).toContainText("삶의 성취 › 진로");                 // 이 기록이 도는 해 › 작은 별
    await shot("03-result", true);
    await parts.getByRole("button", { name: /^같은 주제 \d+$/ }).click();                     // 같은 작은 별의 다른 기록(AI 연결 아님)
    const same = r.getByRole("region", { name: "같은 주제의 다른 기록" });
    await expect(same).toContainText("‘진로’의 다른 기록");
    await expect(same).toContainText("AI가 이어 준 연결은 아니에요");
    await expect(same.getByRole("link").first()).toHaveAttribute("href", /^\/history\?id=e\d+$/);
    await expect(r.getByRole("region", { name: "생각 목록" })).toBeHidden();
  });

  await test.step("피드백 누르기", async () => {
    await page.getByRole("group", { name: "한마디 피드백" }).getByRole("button", { name: "좋아요" }).click();
    await expect(page.getByRole("group", { name: "한마디 피드백" }).getByText("고마워요")).toBeVisible();
    const parts = page.getByRole("group", { name: "나눠 보기" });
    await parts.getByRole("button", { name: /^이어진 생각/ }).click();
    await page.getByRole("group", { name: "이 연결이 맞나요" }).first().getByRole("button", { name: "맞아요" }).click();
    await parts.getByRole("button", { name: /^생각/ }).click();
    await page.getByRole("group", { name: "다짐 상태" }).getByRole("button", { name: "지켰어요" }).click();
    await expect(page.getByText("다짐 지켰어요")).toBeVisible();
    await page.getByRole("button", { name: "같은 사람" }).click();
    await expect(page.getByText("“같은 사람”으로 기억할게요.")).toBeVisible();
    await parts.getByRole("button", { name: "더 보기" }).click();
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
    await card.getByRole("button", { name: "카드 닫기" }).click();
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
    await nav("되고 싶은 모습");
    await page.getByRole("button", { name: "새로 적기" }).click();
    const answers = ["바쁘다는 말로 자꾸 미루는 사람", "어디서든 배우고, 한 약속은 지키는 사람", "피곤하면 다 내일로 미룬다", "피곤하면 오 분만 하고 자겠다"];
    for (const [i, a] of answers.entries()) {
      await page.locator("#asp").fill(a);
      if (i === 2) await shot("09-aspiration-form");
      await page.getByRole("button", { name: "다음", exact: true }).click();
    }
    await page.getByRole("button", { name: "성취" }).click();
    await page.getByRole("button", { name: "규범" }).click();
    await page.getByRole("button", { name: "북극성으로 띄우기" }).click();
    await expect(page.getByText("북극성으로 띄웠어요")).toBeVisible();
    await expect(page.getByRole("region", { name: "지금의 북극성" })).toContainText("어디서든 배우고, 한 약속은 지키는 사람");
    await page.locator("summary", { hasText: "예전 모습 보기" }).click();
    await shot("10-aspiration-saved", true);
  });

  await test.step("설정: 팩폭은 경고 확인 뒤에만", async () => {
    await nav("설정");
    await page.getByRole("group", { name: "설정 묶음" }).getByRole("button", { name: "별지기", exact: true }).click();
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

  await test.step("설정 · 직접 정하기: 원하는 말투를 적어야 고름", async () => {
    await page.getByRole("button", { name: "직접 정하기" }).click();
    const box = page.getByRole("form", { name: "직접 정하기" });
    await expect(page.getByRole("button", { name: "직접 정하기" })).toHaveAttribute("aria-pressed", "false");   // 적기 전엔 안 골라짐
    await expect(box.getByRole("button", { name: "이 말투로 할게요" })).toBeDisabled();
    await box.getByLabel("원하는 말투를 적어 주세요").fill("친한 언니처럼 반말로, 이모지 하나만");
    await expect(box).toContainText("20 / 200");
    await box.getByRole("button", { name: "이 말투로 할게요" }).click();
    await expect(page.getByRole("button", { name: "직접 정하기" })).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: /^팩폭/ }).click();   // 이어지는 흐름은 팩폭으로(경고는 이미 확인함)
    await expect(page.getByRole("button", { name: /^팩폭/ })).toHaveAttribute("aria-pressed", "true");
  });

  await test.step("설정 · 개인정보와 계정 → 개인정보처리방침", async () => {
    await page.getByRole("group", { name: "설정 묶음" }).getByRole("button", { name: "개인정보와 계정" }).click();
    await page.getByRole("link", { name: "개인정보처리방침" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "나의 우주 개인정보처리방침" })).toBeVisible();
  });

  await test.step("위기 글 → 평소 결과 카드 + 안부 한 줄(단체 안내 · 따로 뜨는 화면 없음)", async () => {
    await nav("직접 쓰기");
    await page.getByLabel(/마음껏 적어/).fill(CRISIS);
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    const r = page.getByTestId("result");
    await expect(r).toBeVisible({ timeout: 15_000 });
    const voice = r.getByRole("region", { name: "별지기 한마디" });
    await expect(voice).toContainText("다정하게"); // 팩폭이어도 그 글만 다정하게
    await expect(voice.getByTestId("check-in")).toBeVisible();
    await expect(r.getByRole("region", { name: "생각 목록" })).toBeVisible();
    await expect(page.locator('a[href^="tel:"]')).toHaveCount(0);
    expect(await page.locator("body").innerText(), "단체 이름 · 전화번호").not.toMatch(HOTLINE);
    await shot("12-crisis", true);
  });

  await test.step("끊김 → 이어서 하기", async () => {
    await nav("지난 기록");
    await nav("직접 쓰기");
    await page.getByLabel(/마음껏 적어/).fill(HANEUL + "\n[끊김]");
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    const resume = page.getByRole("button", { name: "이어서 하기" });
    await expect(resume).toBeVisible({ timeout: 15_000 });
    await shot("13-resume");
    await resume.click();
    await expect(page.getByTestId("result")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("region", { name: "별지기 한마디" })).toContainText("팩폭"); // 바꾼 말투가 반영됨
  });

  await test.step("사람 지우기(이름을 관계 말로, 가족을 부르는 이름은 묶음 말로)", async () => {
    await nav("사람");
    await page.getByRole("button", { name: /^엄마/ }).click();
    await page.getByRole("button", { name: "엄마 지우기" }).click();
    const mom = page.getByRole("alertdialog", { name: "엄마 지우기 확인" });
    await expect(mom).toContainText("엄마를 지우면, 저장된 글 속 “엄마”를 “부모”로 바꿔요.");   // 2026-10-28 동규: 엄마 → 부모
    await mom.getByRole("button", { name: "취소" }).click();
    if (info.project.use.isMobile) await page.getByRole("button", { name: "사람 목록으로" }).click();
    await page.getByRole("button", { name: /^지은/ }).click();
    await page.getByRole("button", { name: "지은 지우기" }).click();
    const dlg = page.getByRole("alertdialog", { name: "지은 지우기 확인" });
    await expect(dlg).toContainText("“지은”을 “동생”으로 바꿔요");
    await expect(dlg).toContainText("문장 · 생각 · 이어진 선은 그대로");
    await shot("14-people-delete", true);
    await dlg.getByRole("button", { name: "지우기" }).click();
    await expect(page.getByText("지은을 지웠어요. 글 1곳의 이름을 “동생”으로 바꿨어요.")).toBeVisible();
  });

  await test.step("지난 기록: 달력 → 그날 기록 → 돌아오기 · 사이드바 작은 달력 · 주제별", async () => {
    await nav("지난 기록");
    const main = page.getByRole("main");
    await expect(main.getByRole("heading", { name: "10월 3일 토요일" })).toBeVisible();   // 처음엔 가장 최근 기록의 날
    await expect(main.getByRole("button", { name: /10\/3 토요일 일기/ }).first()).toBeVisible();
    await shot("15-history");
    await main.getByRole("button", { name: "이전 달" }).click();
    await main.getByRole("button", { name: "9월 20일, 기록 1편" }).click();
    await main.getByRole("button", { name: /9\/20 토요일 일기/ }).click();
    await expect(page).toHaveURL(/\/history\?id=e16/);
    await expect(page.getByTestId("result")).toBeVisible();
    await page.getByRole("button", { name: "← 목록으로 돌아가기" }).click();
    await expect(main.getByRole("heading", { name: "9월 20일 일요일" })).toBeVisible();   // 고른 날 그대로

    const side = page.getByRole("complementary", { name: "사이드바" });
    const drawer = !(await side.isVisible());
    if (drawer) await page.getByRole("button", { name: "메뉴 열기 · 닫기" }).click();
    await side.getByRole("button", { name: "9월 12일, 기록 1편" }).click();   // 작은 달력도 고른 날의 달(9월)
    await expect(page).toHaveURL(/\/history\?day=2026-09-12/);
    await expect(main.getByRole("button", { name: /9\/12 작은 회사 탐방/ })).toBeVisible();
    if (drawer) await expect(side).toBeHidden();

    await main.getByRole("button", { name: "주제별" }).click();
    await expect(main.getByRole("button", { name: /^진로, 기록/ })).toHaveAttribute("aria-pressed", "true");   // 가장 많은 작은 별
    await main.getByRole("button", { name: /^아침 걷기, 기록/ }).click();
    await expect(main.getByRole("heading", { name: "건강 › 아침 걷기" })).toBeVisible();
    await expect(main.getByRole("button", { name: /7\/10 걷기 2주째/ })).toBeVisible();
  });

  expect(errors, "화면 오류가 없어야 함").toEqual([]);
});
