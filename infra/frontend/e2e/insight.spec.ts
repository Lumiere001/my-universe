// 나에 대해 알게 된 것(docs/content/U-11, GET /insight): 우주의 떠 있는 단추 '알게 된 것'으로 열고, 해마다 자주 쓴 주제 | 다섯 묶음(접는 칸),
// 날짜와 원문 인용만, 날짜를 누르면 그 기록, 글을 쓰면 바뀐 생각이 생김, 한 화면에 들어감, 비었을 때 · 이어진 생각이 없을 때 · 실패.
// 가짜 데이터(가상 인물 하늘, lib/mock.ts). 기록이 많은 모양은 window.__insight 에 가상 인물 김도윤(eval/personas/pD, 두 영역 모드)의 /insight 결과를 넣는다.
// 캡처는 docs/screens/ws-insight/<기기>-NN-이름.png
import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import two from "./fixtures/insight-two.json";
import { nav } from "./menu";

const OUT = path.resolve(__dirname, "../../../docs/screens/ws-insight");
const group = (page: Page, name: string) => page.getByRole("region", { name: "생각 묶음" }).locator("details").filter({ has: page.locator("summary", { hasText: name }) });
const oneScreen = async (page: Page) => {
  expect(await page.evaluate(() => document.documentElement.scrollHeight - innerHeight), "한 화면에").toBeLessThanOrEqual(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth), "가로로 넘치지 않음").toBeLessThanOrEqual(1);
};
const fake = (page: Page, v: unknown) => page.addInitScript((x) => { (window as unknown as { __insight: unknown }).__insight = x; }, v);

test("나에 대해 알게 된 것", async ({ page }, info) => {
  const dev = info.project.name;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${dev}-${name}.png` });

  await test.step("우주의 '알게 된 것' → 첫 해(삶의 성취): 자주 쓴 주제 · 처음에는 내용이 있는 첫 묶음만 펼침", async () => {
    await page.goto("/universe");
    await expect(page.locator(".uni canvas")).toBeVisible();
    await page.waitForTimeout(800);
    await shot("00-universe-entry");
    await page.getByRole("group", { name: "우주 도구" }).getByRole("link", { name: "알게 된 것" }).click();
    await page.waitForURL("**/insight");
    await expect(page.locator(".crumb")).toHaveText("나의 우주 › 우주 › 알게 된 것");
    await expect(page.getByRole("heading", { level: 1, name: "나에 대해 알게 된 것" })).toBeAttached();
    await expect(page.getByText("2026-03-08 ~ 2026-09-20에 남긴 기록 17편에서")).toBeVisible();
    const suns = page.getByRole("group", { name: "해 고르기" });
    await expect(suns.getByRole("button")).toHaveCount(5);
    await expect(suns.getByRole("button", { name: /삶의 성취/ })).toHaveAttribute("aria-pressed", "true");
    const stars = page.getByRole("region", { name: "자주 쓴 주제" });
    await expect(stars.locator("li").first()).toContainText("진로 5편 · 2026-03-14 ~ 2026-09-20");
    await expect(stars).toContainText("아쉬웠던 점 1");                     // 생각 종류는 보이는 이름으로
    await expect(group(page, "이어 온 생각")).toHaveAttribute("open", "");
    await expect(group(page, "이어 온 생각")).toContainText("2번 이어졌어요");
    await expect(group(page, "이어 온 생각")).toContainText("처음 2026-05-30: “작은 회사에 가면 빨리 배운다고 했다”");
    await expect(group(page, "바뀐 생각").locator("summary")).toContainText("0");
    await expect(group(page, "아직 맞서는 생각")).not.toHaveAttribute("open", "");
    await expect(page.locator("main")).not.toContainText(/당신은|한 사람이에요/);   // 사람을 판정하지 않는다
    await oneScreen(page);
    await shot("01-first-sun");
  });

  await test.step("접힌 묶음 펼치기: 맞서는 생각(축 · AI 추정 · 주황), 다른 영역과 이어진 생각(고른 해가 낀 것만)", async () => {
    await group(page, "아직 맞서는 생각").locator("summary").click();
    const open = group(page, "아직 맞서는 생각");
    await expect(open).toContainText("진로· 안정 ↔ 배움점선 · AI 추정");
    await expect(open.locator(".quote.o")).toHaveCount(2);
    await group(page, "다른 영역과 이어진 생각").locator("summary").click();
    const across = group(page, "다른 영역과 이어진 생각");
    await expect(across.locator("li")).toHaveCount(2);                     // 목표 충돌(공동체) · 긴장(영성·신앙). 공동체 ↔ 관계는 빠짐
    await expect(across).toContainText("영성·신앙 2026-06-07: “이미 충분하다”");
    await expect(open).not.toHaveAttribute("open", "");                   // 한 번에 하나만 펼침
    await oneScreen(page);
    await shot("02-groups-open");
  });

  await test.step("해 바꾸기(관계): 정리된 생각이 첫 묶음, 날짜를 누르면 그 기록", async () => {
    await page.getByRole("group", { name: "해 고르기" }).getByRole("button", { name: /^관계/ }).click();
    await expect(group(page, "정리된 생각")).toHaveAttribute("open", "");
    await expect(group(page, "정리된 생각")).toContainText("정리 2026-06-20: “혼자는 충전, 함께는 성장”");
    await expect(group(page, "이어 온 생각")).toContainText("같은 주제를 다시 쓰면 이어 온 생각이 여기에 모여요.");
    await group(page, "정리된 생각").getByRole("link", { name: "2026-06-20" }).click();
    await page.waitForURL(/\/history\?id=e11$/);
    await expect(page.getByRole("button", { name: "← 목록으로 돌아가기" })).toBeVisible();
  });

  await test.step("글을 쓰면 바뀐 생각이 생긴다(그때 3/14 → 지금 10/3, 실선)", async () => {
    await nav(page, "직접 쓰기");
    await page.getByLabel(/마음껏 적어/).fill("가상 인물 하늘의 글. 관심 있는 팀을 찾아보기로 했지만 또 미뤘다. 그래도 배우는 느낌이 중요하다는 걸 알았다.");
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    await expect(page.getByTestId("result")).toBeVisible({ timeout: 30_000 });
    await nav(page, "우주");
    await page.getByRole("group", { name: "우주 도구" }).getByRole("link", { name: "알게 된 것" }).click();
    await page.waitForURL("**/insight");
    await expect(page.getByText("2026-03-08 ~ 2026-10-03에 남긴 기록 18편에서")).toBeVisible();
    await group(page, "바뀐 생각").locator("summary").click();
    const changed = group(page, "바뀐 생각");
    await expect(changed).toContainText("실선 · 글에 직접 씀");
    await expect(changed).toContainText("그때 2026-03-14: “큰 회사에 들어가는 게 맞다.”");
    await expect(changed).toContainText("지금 2026-10-03:");
    await oneScreen(page);
    await shot("03-changed-after-writing");
  });
  expect(errors).toEqual([]);
});

test("기록이 많을 때(두 영역 모드) 한 화면 · 목록은 칸 안에서만", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await fake(page, two);
  await page.goto("/insight");
  await expect(page.getByText("2026-07-01 ~ 2026-10-25에 남긴 기록 19편에서")).toBeVisible();
  await expect(page.getByRole("group", { name: "해 고르기" }).getByRole("button")).toHaveText(["커리어 15편", "인간관계 15편"]);
  await expect(page.getByRole("region", { name: "자주 쓴 주제" }).locator("li")).toHaveCount(two.suns[0].stars.length);
  await expect(group(page, "이어 온 생각")).toContainText("영어 녹음의 정확성· 8번 이어졌어요");
  await group(page, "바뀐 생각").locator("summary").click();
  await expect(group(page, "바뀐 생각")).toContainText("맞는 문장만 말하기 ↔ 끝까지 말해 보기");
  for (const s of await page.getByRole("region", { name: "생각 묶음" }).locator("summary").all())
    await expect(s, "펼친 묶음이 길어도 다섯 묶음 제목은 화면 안에").toBeInViewport();
  await oneScreen(page);
  await page.screenshot({ path: `${OUT}/${info.project.name}-04-many-two-domain.png` });
  expect(errors).toEqual([]);
});

test("비었을 때 · 이어진 생각이 없을 때 · 불러오지 못했을 때", async ({ page }, info) => {
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${info.project.name}-${name}.png` });
  await fake(page, { period: null, suns: [], across: [] });
  await page.goto("/insight");
  await expect(page.getByText("아직 모을 생각이 없어요.")).toBeVisible();
  await expect(page.locator("main").getByRole("link", { name: "직접 쓰기" })).toHaveAttribute("href", "/write");
  await shot("05-empty");

  const end = { day: "2026-10-01", quote: "아침에 걸었다", record_id: "e1", thought_id: "t1" };
  await page.evaluate((x) => { (window as unknown as { __insight: unknown }).__insight = x; }, {
    period: { from: "2026-10-01", to: "2026-10-01", records: 1 },
    suns: [{ name: "건강", records: 1, stars: [{ name: "아침 걷기", records: 1, first: end.day, last: end.day, kinds: { 다짐: 1 } }], kept: [], changed: [], open: [], settled: [] }],
    across: [] });
  await nav(page, "우주");
  await page.getByRole("group", { name: "우주 도구" }).getByRole("link", { name: "알게 된 것" }).click();
  await expect(page.getByText("2026-10-01에 남긴 기록 1편에서")).toBeVisible();      // 하루면 날짜 하나
  await expect(page.getByRole("status").filter({ hasText: "아직 서로 이어진 생각이 없어요." })).toBeVisible();
  await expect(page.getByRole("group", { name: "해 고르기" })).toHaveCount(0);   // 해가 하나면 고르기 없음
  await expect(page.getByRole("region", { name: "자주 쓴 주제" })).toContainText("아침 걷기 1편 · 2026-10-01");
  await expect(page.locator(".ins-groups details[open]")).toHaveCount(0);
  await shot("06-few-records");

  await page.evaluate(() => { (window as unknown as { __insight: unknown }).__insight = "fail"; });
  await nav(page, "우주");
  await page.getByRole("group", { name: "우주 도구" }).getByRole("link", { name: "알게 된 것" }).click();
  await expect(page.locator("main").getByRole("alert")).toHaveText("알게 된 것을 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.");
});
