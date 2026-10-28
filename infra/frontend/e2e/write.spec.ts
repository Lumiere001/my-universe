// WS13 쓰기 화면 작은 묶음(가짜 데이터 모드): 말풍선(날씨 질문 · 다짐 안부) → 다음부터 묻지 않기 → 어제 날짜 · 제목으로 쓰기 → 말풍선에 지난 질문
// → .md · .txt 불러와 결과 → 같은 글 다시 보내면 '이미 정리한 글' → 날짜 확인 필요 → 고치기 → 지우면 목록 · 우주에서 사라짐 → 별지기 이름.
// 캡처는 남기지 않는다(실제 백엔드 캡처는 e2e-real/ws13.spec.ts). 모두 가상 인물 하늘의 글 · 지어낸 글.
import { expect, test } from "@playwright/test";
import { nav as menuNav } from "./menu";

const ymd = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
const YESTERDAY = ymd(new Date(Date.now() - 86_400_000));
const MD = "# 9/25 독서노트 — 『작은 습관의 힘』\n\n## 읽은 것\n습관은 의지가 아니라 환경에서 시작된다는 장을 읽었다.\n#작은습관";
const TXT = "산책\n저녁에 동네를 한 바퀴 걸었다. 바람이 시원했다.";

test("쓰기 화면 작은 묶음", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const nav = (name: string) => menuNav(page, name);
  const bubble = page.getByRole("region", { name: "별지기 말풍선" });
  const submit = () => page.getByRole("button", { name: "우주에 띄우기" }).click();
  const result = page.getByTestId("result");
  const again = async () => { await page.getByRole("button", { name: "새 글 쓰기" }).click(); await expect(page.getByLabel(/마음껏 적어/)).toBeVisible(); };

  await test.step("말풍선(접힌 한 줄 → 누르면 펼침): 날씨 질문 + 다짐 안부 → 건너뛰면 날씨 질문 없음", async () => {
    await page.goto("/write");
    await expect(bubble.locator("summary")).toContainText("마음 날씨");          // 접힌 줄에 첫 문장 · 다짐 안부 표시
    await expect(bubble.locator("summary")).toContainText("다짐 안부");
    await expect(bubble.getByTestId("prompt-vow")).toBeHidden();
    await bubble.locator("summary").click();
    await expect(bubble.getByTestId("prompt-question")).toContainText("마음 날씨");
    await expect(bubble.getByTestId("prompt-vow")).toContainText("팀 세 곳");
    await bubble.getByRole("button", { name: "다음부터 묻지 않기" }).click();
    await expect(bubble.getByText("다음부터 마음 날씨는 묻지 않을게요")).toBeVisible();
    await nav("지난 기록"); await nav("직접 쓰기");
    await bubble.locator("summary").click();
    await expect(bubble.getByTestId("prompt-vow")).toBeVisible();
    await expect(bubble.getByTestId("prompt-question")).toHaveCount(0);
  });

  await test.step("일기장: 날짜 줄 = 글이 다루는 날 · 마크다운 미리보기(글 속 태그는 글자로)", async () => {
    await expect(page.locator(".diary-date")).toContainText(/\d+월 \d+일 .요일/);
    const box = page.getByLabel(/마음껏 적어/);
    await box.fill("# 산책\n바람이 **시원했다**. *조금* 걸었다.\n둘째 줄\n\n- 공원\n- 편지\n\n1. 하나\n\n> 내일도\n\n---\n<b>태그</b> 2 * 3 * 4");
    await page.getByRole("button", { name: "미리보기" }).click();
    const view = page.getByRole("article", { name: "미리보기" });
    await expect(view.getByRole("heading", { name: "산책" })).toBeVisible();
    await expect(view.locator("strong")).toHaveText("시원했다");
    await expect(view.locator("em")).toHaveText("조금");
    await expect(view.locator("p br")).toHaveCount(1);                                // 줄바꿈
    await expect(view.locator("ul li")).toHaveCount(2);
    await expect(view.locator("ol li")).toHaveCount(1);
    await expect(view.locator("blockquote")).toHaveText("내일도");
    await expect(view.locator("hr")).toHaveCount(1);
    await expect(view.locator("b")).toHaveCount(0);                                   // HTML 은 그리지 않음
    await expect(view).toContainText("<b>태그</b> 2 * 3 * 4");
    await expect(box).toBeHidden();
    await page.getByRole("button", { name: "쓰기", exact: true }).click();
    await expect(box).toHaveValue(/^# 산책\n/);                                       // 별지기에게는 쓴 글 그대로
    await box.fill("");
    await bubble.locator("summary").click();                                          // 말풍선을 다시 접으면
    expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1), "일기장이 한 화면에").toBe(true);
  });

  await test.step("어제 날짜 · 제목으로 쓰면 결과의 날이 어제", async () => {
    await page.getByLabel(/제목/).fill("어제 쓴 일기");
    await page.getByLabel(/글이 다루는 날/).fill(YESTERDAY);
    await page.getByLabel(/마음껏 적어/).fill("어제는 도서관에서 오래 공부했다.\n다음 주에는 한 곳이라도 먼저 메일을 보내 보고 싶다.");
    await submit();
    await expect(result).toBeVisible({ timeout: 15_000 });
    await expect(result.getByTestId("entry-day")).toContainText(YESTERDAY);
    await expect(result.getByRole("heading", { name: "어제 쓴 일기" })).toBeVisible();
    // 줄바꿈이 보이게(pre-line)
    await expect(result.getByRole("region", { name: "별지기 한마디" }).locator(".bubble p")).toHaveCSS("white-space", "pre-line");
  });

  await test.step("말풍선에 지난번 '다음에 써 볼 질문'", async () => {
    await again();
    await expect(bubble.getByTestId("prompt-question")).toContainText("부모님께는 어떤 말부터");
  });

  await test.step(".md · .txt 불러와 결과 받기(파일 이름 속 날짜 → 날)", async () => {
    const file = page.getByLabel("글 파일(.txt · .md)에서 불러오기");
    await file.setInputFiles({ name: "보고서.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF") });
    await expect(page.getByText(".txt · .md 파일만 불러올 수 있어요.")).toBeVisible();
    await file.setInputFiles({ name: "2026-09-25-독서노트.md", mimeType: "text/markdown", buffer: Buffer.from(MD) });
    await expect(page.getByLabel(/제목/)).toHaveValue("9/25 독서노트 — 『작은 습관의 힘』");
    await expect(page.getByLabel(/글이 다루는 날/)).toHaveValue("2026-09-25");
    await expect(page.getByLabel(/마음껏 적어/)).toHaveValue("읽은 것\n습관은 의지가 아니라 환경에서 시작된다는 장을 읽었다.\n#작은습관");
    await submit();
    await expect(result.getByTestId("entry-day")).toContainText("2026-09-25", { timeout: 15_000 });
    await again();
    await file.setInputFiles({ name: "산책.txt", mimeType: "text/plain", buffer: Buffer.from(TXT) });
    await expect(page.getByLabel(/제목/)).toHaveValue("산책");
    await submit();
    await expect(result).toBeVisible({ timeout: 15_000 });
    await expect(result.getByRole("heading", { name: "산책" })).toBeVisible();
    await expect(page.getByRole("link", { name: "예시 일기 내려받기" })).toHaveCount(0);   // 결과 화면엔 없음
  });

  await test.step("같은 글을 다시 보내면 '이미 정리한 글이에요' + 그 기록으로 가는 링크", async () => {
    await again();
    await page.getByLabel("글 파일(.txt · .md)에서 불러오기").setInputFiles({ name: "산책.txt", mimeType: "text/plain", buffer: Buffer.from(TXT) });
    await submit();
    const dup = page.getByRole("status", { name: "이미 정리한 글" });
    await expect(dup).toContainText("이미 정리한 글이에요", { timeout: 15_000 });
    await dup.getByRole("link", { name: "지난 기록에서 보기" }).click();
    await expect(page).toHaveURL(/\/history\?id=/);
    await expect(result.getByRole("heading", { name: "산책" })).toBeVisible();
    await nav("직접 쓰기");
  });

  await test.step("날짜 확인 필요 → 날짜 고르기", async () => {
    await page.getByLabel(/제목/).fill("3/27~3/29 제주 여행");
    await page.getByLabel(/마음껏 적어/).fill("사흘 동안 바다를 보고 왔다.");
    await submit();
    const fix = result.getByTestId("day-fix");
    await expect(fix).toContainText("날짜 확인 필요", { timeout: 15_000 });
    await fix.getByLabel("글이 다루는 날").fill("2026-03-28");
    await fix.getByRole("button", { name: "이 날로 고치기" }).click();
    await expect(result.getByTestId("entry-day")).toContainText("2026-03-28");
    await expect(result.getByTestId("day-fix")).toHaveCount(0);
  });

  await test.step("지난 기록 지우기 → 목록 · 우주에서 사라짐", async () => {
    await nav("지난 기록");
    await page.getByRole("searchbox", { name: "찾기" }).fill("제주");   // 3/28 로 고친 기록: 찾기로 바로
    const item = page.getByRole("button", { name: /3\/27~3\/29 제주 여행/ });
    await item.click();
    await page.getByRole("button", { name: "이 기록 지우기" }).click();
    await page.getByRole("alertdialog", { name: "기록 지우기 확인" }).getByRole("button", { name: "지우기" }).click();
    await expect(page.getByText("기록을 지웠어요.")).toBeVisible();
    await expect(item).toHaveCount(0);
    await nav("우주");
    await page.getByText("목록에서 기록 고르기").click();
    await expect(page.getByRole("button", { name: "산책" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: /제주 여행/ })).toHaveCount(0);
  });

  await test.step("별지기 이름 바꾸기 → 말풍선 이름표", async () => {
    await nav("설정");
    await page.getByLabel("별지기 이름").fill("달지기");
    await page.getByRole("button", { name: "이름 바꾸기" }).click();
    await expect(page.getByText("저장했어요.")).toBeVisible();
    await nav("직접 쓰기");
    await expect(bubble).toContainText("달지기");
  });

  expect(errors, "화면 오류가 없어야 함").toEqual([]);
});
