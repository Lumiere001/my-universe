// WS14 우주 화면(가짜 데이터 · 가상 인물 하늘): 행성 크기 = 생각 수 · 밝기 = 확신 · '?' = 열린 질문 · 연결이 가장 많은 해가 가운데,
// 행성 → 원문 인용(그때 → 지금) · 결과 카드 링크, 북극성 → 닿은 순간 목록 + 그 행성 빛남, 사람 → 얽힌 생각 시간순 목록, 끝난 목표 충돌 구분.
// 캡처는 docs/screens/ws14/<기기>-NN-이름.png
import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import { centerSun, planetLook } from "../components/universeLook";

const OUT = path.resolve(__dirname, "../../../docs/screens/ws14");
type Uni = { xy: (i: string) => { x: number; y: number }; center: () => string;
  look: (i: string) => { scale: number; bright: number; lit: boolean } };
// 시험 창구(Universe3D 의 window.__uni): 행성 화면 좌표 · 그려진 크기 · 밝기 · 빛남, 가운데 해
const look = (page: Page, id: string) => page.evaluate((i) => (window as unknown as { __uni: Uni }).__uni.look(i), id);
const lit = (page: Page, id: string) => look(page, id).then((x) => x.lit);

test.describe("값 → 모양(화면 단위)", () => {
  test("행성 크기는 생각 수, 밝기는 확신에 따라 다르다", () => {
    expect(planetLook({ thought_count: 5 }).scale).toBeGreaterThan(planetLook({ thought_count: 1 }).scale);
    expect(planetLook({ thought_count: 1 }).scale).toBe(1);
    expect(planetLook({ thought_count: 400 }).scale).toBeLessThanOrEqual(1.8);   // 아주 많아도 궤도를 덮지 않게
    const b = (c: string | null) => planetLook({ certainty: c }).light;
    expect(b("단정")).toBeGreaterThan(b("고민 중"));
    expect(b("고민 중")).toBeGreaterThan(b("판단 보류"));
    expect(b(null)).toBe(b("고민 중"));
  });

  test("다른 태양계와 이어진 선이 가장 많은 해가 가운데(기록 수보다 먼저)", () => {
    const planets = [["a1", "A"], ["a2", "A"], ["a3", "A"], ["b1", "B"], ["c1", "C"], ["c2", "C"]]
      .map(([id, sun_id]) => ({ id, sun_id, star_id: "", written_at: "", title: "", order: 0, ring: false, people: [], weather: null }));
    const suns = [{ id: "A", planet_count: 3 }, { id: "B", planet_count: 1 }, { id: "C", planet_count: 2 }]
      .map((s) => ({ ...s, name: s.id, custom: false }));
    const link = (from_planet: string, to_planet: string) =>
      ({ id: from_planet + to_planet, from_planet, to_planet, type: "이어짐", line: "실선" as const, cross_domain: true, needs_confirm: false, explanation: "" });
    // B 는 기록이 가장 적지만 A · C 와 이어져 있다(같은 해 안의 선 a1-a2 는 세지 않음)
    expect(centerSun({ suns, planets, links: [link("a1", "a2"), link("b1", "a3"), link("c1", "b1")], twins: [] })).toBe("B");
    // 쌍행성도 선으로 센다
    expect(centerSun({ suns, planets, links: [], twins: [{ id: "w", a_planet: "c1", b_planet: "a1", topic: "", status: "열림" }] })).toBe("A");
    // 선이 없으면 기록이 많은 해
    expect(centerSun({ suns, planets, links: [], twins: [] })).toBe("A");
  });
});

test("우주 화면", async ({ page }, info) => {
  const dev = info.project.name;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${dev}-${name}.png` });
  const tapAt = async (id: string) => {
    const { x, y } = await page.evaluate((i) => (window as unknown as { __uni: Uni }).__uni.xy(i), id);
    if (info.project.use.hasTouch) await page.touchscreen.tap(x, y); else await page.mouse.click(x, y);
  };

  await page.goto("/universe");
  await expect(page.locator(".uni canvas")).toBeVisible();
  await page.waitForTimeout(800);

  await test.step("크기 · 밝기 · '?' · 가운데 해", async () => {
    const big = await look(page, "e16"), small = await look(page, "e07");   // 생각 5개 vs 1개
    expect(big.scale).toBeGreaterThan(small.scale);
    const sure = await look(page, "e11"), unsure = await look(page, "e14");  // 단정 vs 판단 보류
    expect(sure.bright).toBeGreaterThan(unsure.bright);
    await expect(page.locator(".uni .lab.q")).toHaveCount(3);                     // 열린 질문이 있는 행성 3개
    expect(await page.evaluate(() => (window as unknown as { __uni: Uni }).__uni.center())).toBe("d1");  // 삶의 성취: d4 · d5 와 이어짐(d4 와 같은 수, 기록이 더 많음)
    await shot("01-universe");
  });

  await test.step("행성 → 원문 인용 · 그때 → 지금 · 결과 카드 링크", async () => {
    await tapAt("e11");
    const card = page.getByTestId("planet-card");
    await expect(card).toContainText("“혼자는 충전, 함께는 성장”");               // 생각의 원문 인용
    await expect(card).toContainText("그때 2026-04-05: “혼자 있는 시간이 가장 편하다”");
    await expect(card).toContainText("지금 2026-06-20: “혼자는 충전, 함께는 성장”");
    await shot("02-planet-quotes");
    await card.getByRole("link", { name: "결과 카드 보기" }).click();
    await expect(page).toHaveURL(/\/universe\/e11$/);
    const r = page.getByTestId("result");
    await expect(r.getByRole("region", { name: "생각 목록" })).toContainText("혼자는 충전, 함께는 성장이다.");
    await shot("03-result-card");
    await page.getByRole("link", { name: "← 우주로" }).click();
    await expect(page.locator(".uni canvas")).toBeVisible();
    await page.waitForTimeout(500);
  });

  await test.step("끝난 목표 충돌은 따로 보임", async () => {
    await tapAt("e16");
    const card = page.getByTestId("planet-card");
    await expect(card).toContainText("목표 충돌");
    await expect(card).toContainText("끝난 충돌");
    await card.getByRole("button", { name: "닫기" }).click();
  });

  await test.step("북극성 → 닿은 순간 목록 + 그 행성 빛남", async () => {
    expect(await lit(page, "e12")).toBe(false);
    await tapAt("north");
    const card = page.getByRole("region", { name: "북극성" });
    await expect(card.getByTestId("north-reached")).toContainText("“걷기를 2주째 이어 가고 있다”");
    await expect(card.getByTestId("north-reached")).toContainText("7/10 걷기 2주째");
    await expect.poll(() => lit(page, "e12")).toBe(true);
    expect(await lit(page, "e11")).toBe(false);
    await shot("04-north-reached");
    await card.getByRole("button", { name: "닫기" }).click();
    await expect.poll(() => lit(page, "e12")).toBe(false);
  });

  await test.step("사람 → 얽힌 생각 시간순 목록 + 그 행성 빛남", async () => {
    await page.getByRole("group", { name: "사람 고르기" }).getByRole("button", { name: /민수/ }).click();
    const list = page.getByTestId("person-thoughts");
    await expect(list.locator("li")).toHaveCount(3);
    const days = await list.locator("li .sub").allTextContents();
    expect(days.map((d) => d.slice(0, 10))).toEqual(["2026-03-27", "2026-05-30", "2026-09-20"]);
    await expect(list).toContainText("“형이 먼저 안부를 물어봐 줬다”");
    await expect.poll(() => lit(page, "e09")).toBe(true);
    await shot("05-person-thoughts");
    await list.getByRole("button", { name: /5\/30 선배와 대화/ }).click();          // 목록에서 그 행성 카드로
    await expect(page.getByTestId("planet-card")).toContainText("5/30 선배와 대화");
  });

  await test.step("사람 목록 화면에서도 얽힌 생각", async () => {
    await page.goto("/people");
    await page.getByRole("button", { name: "민수과(와) 얽힌 생각" }).click();
    await expect(page.getByTestId("person-thoughts").locator("li")).toHaveCount(3);
    await shot("06-people-thoughts");
  });

  expect(errors).toEqual([]);
});
