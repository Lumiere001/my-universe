// WS25 꾸미기(가짜 데이터 · 가상 인물 하늘): 설정에서 우주 테마를 고르면 우주 색이 바뀜, 별지기 모습을 고르면 말풍선 그림이 바뀜,
// 일기에서 처음 나온 해 · 작은 별 · 사람을 결과 카드에서 별지기가 알려 줌(우주 넓히기). 동규가 고를 캡처는 docs/screens/ws25/<기기>-NN-이름.png
// 가짜 데이터는 브라우저 메모리에 있어 page.goto 하면 설정이 처음으로 돌아간다 → 화면 이동은 위 막대 링크로.
import { expect, test, type Page } from "@playwright/test";
import { nav as menuNav } from "./menu";
import path from "node:path";
import { COLOR, grewFrom, THEMES, themeColors, type ThemeName } from "../components/universeLook";

const OUT = path.resolve(__dirname, "../../../docs/screens/ws25");
const FILE: Record<ThemeName, string> = { 밤하늘: "night", 새벽: "dawn", 오로라: "aurora", 먹: "ink" };
const bg = (page: Page) => page.evaluate(() => (window as unknown as { __uni: { bg: () => number } }).__uni.bg());

test.describe("값 → 모양(화면 단위)", () => {
  test("테마는 바탕 · 해 색만 바꾸고, 뜻이 있는 색은 그대로. 모르는 이름이면 기본", () => {
    expect(themeColors("오로라").bg).not.toBe(themeColors("밤하늘").bg);
    expect(themeColors(null).bg).toBe(COLOR.bg);
    expect(themeColors("무지개").sun).toEqual(THEMES["밤하늘"].sun);
    for (const t of Object.keys(THEMES)) {
      const c = themeColors(t);
      expect([c.violet, c.orange, c.gold, c.ended, c.hole]).toEqual([COLOR.violet, COLOR.orange, COLOR.gold, COLOR.ended, COLOR.hole]);
      expect(c.sun.length).toBeGreaterThanOrEqual(5);
    }
  });

  test("우주 넓히기: 먼저 쓴 기록 순서로 이 기록이 처음인 해 · 작은 별 · 사람만", () => {
    const P = (id: string, sun_id: string, star_id: string, day: string) => ({ id, sun_id, star_id, written_at: `${day}T22:00:00+09:00` });
    const d = {
      suns: [{ id: "A", name: "관계", custom: false, planet_count: 2 }, { id: "B", name: "건강", custom: false, planet_count: 1 }],
      stars: [{ id: "a1", sun_id: "A", name: "가족", planet_count: 1 }, { id: "a2", sun_id: "A", name: "친구", planet_count: 1 },
        { id: "b1", sun_id: "B", name: "걷기", planet_count: 1 }],
      planets: [P("e1", "A", "a2", "2026-03-01"), P("e2", "A", "a1", "2026-03-05"), P("e3", "B", "b1", "2026-03-05")]
        .map((p) => ({ ...p, title: "", order: 0, ring: false, people: [], weather: null })),
      people: [{ id: "p1", name: "민수", relation: "선배", planets: ["e2", "e1"] }, { id: "p2", name: "지은", relation: "동생", planets: ["e2"] }],
    };
    expect(grewFrom(d, "e2")).toEqual({ suns: [], stars: ["가족"], people: ["지은"] });         // 관계 · 민수는 e1 이 먼저
    expect(grewFrom(d, "e3")).toEqual({ suns: ["건강"], stars: ["걷기"], people: [] });
    expect(grewFrom(d, "e1")).toEqual({ suns: ["관계"], stars: ["친구"], people: ["민수"] });
    expect(grewFrom(d, "없음")).toEqual({ suns: [], stars: [], people: [] });
  });
});

test("꾸미기", async ({ page }, info) => {
  const dev = info.project.name;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${dev}-${name}.png` });
  const nav = (name: string) => menuNav(page, name);
  // 설정은 묶음 하나씩 보인다(2026-10-28): 테마는 '우주와 화면', 별지기 모습은 '별지기'
  const group = (name: string) => page.getByRole("group", { name: "설정 묶음" }).getByRole("button", { name, exact: true }).click();
  const themes = page.getByRole("group", { name: "우주 테마" });

  await page.goto("/universe");
  await expect(page.locator(".uni canvas")).toBeVisible();
  await expect.poll(() => bg(page)).toBe(THEMES["밤하늘"].bg);   // 기본 = 예전 모습
  await expect(page.getByTestId("universe")).toHaveAttribute("data-theme", "밤하늘");

  await test.step("설정에서 테마를 고르면 우주 색이 바뀜(네 벌 캡처)", async () => {
    for (const [i, t] of (["새벽", "오로라", "먹", "밤하늘"] as ThemeName[]).entries()) {
      await nav("설정");
      await group("우주와 화면");
      await themes.getByRole("button", { name: t }).click();
      await expect(themes.getByRole("button", { name: t })).toHaveAttribute("aria-pressed", "true");
      await nav("우주");
      await expect(page.locator(".uni canvas")).toBeVisible();
      await expect.poll(() => bg(page)).toBe(THEMES[t].bg);
      await expect(page.getByTestId("universe")).toHaveAttribute("data-theme", t);
      await page.waitForTimeout(400);
      await shot(`0${i + 1}-theme-${FILE[t]}`);
    }
  });

  await test.step("/me 가 늦게 와 테마로 다시 그려도 영역 넘는 선은 숨김(눌렀을 때)", async () => {
    const uni = (k: "bg" | "cross") => page.evaluate((key) => (window as unknown as { __uni?: Record<string, () => number> }).__uni?.[key]() ?? null, k);
    await nav("설정");
    await group("우주와 화면");
    await themes.getByRole("button", { name: "오로라" }).click();
    await page.evaluate(() => { const w = window as unknown as { __uni?: unknown; __slowMe?: number }; delete w.__uni; w.__slowMe = 1500; });
    await nav("우주");
    await expect.poll(() => uni("bg")).toBe(THEMES["밤하늘"].bg);   // /me 전: 기본 색
    expect(await uni("cross")).toBe(0);
    await expect.poll(() => uni("bg"), { timeout: 5000 }).toBe(THEMES["오로라"].bg);   // /me 뒤: 테마로 다시 그림
    expect(await uni("cross")).toBe(0);
    await page.evaluate(() => { delete (window as unknown as { __slowMe?: number }).__slowMe; });
  });

  await test.step("별지기 모습을 고르면 말풍선 그림이 바뀜", async () => {
    await nav("설정");
    await group("별지기");
    const looks = page.getByRole("group", { name: "별지기 모습" });
    await expect(looks.getByRole("button", { name: "이름 글자" })).toHaveAttribute("aria-pressed", "true");   // 기본
    const who = page.getByRole("region", { name: "말투" }).locator(".voice .who");
    await expect(who).toHaveText("별");
    for (const [k, f] of [["별", "star"], ["달", "moon"], ["행성", "planet"], ["고양이", "cat"]]) {
      await looks.getByRole("button", { name: k, exact: true }).click();
      await expect(page.locator("html")).toHaveAttribute("data-keeper", f);
      await expect(who).toHaveCSS("background-image", new RegExp(`/keeper/${f}\\.svg`));
    }
    await looks.scrollIntoViewIfNeeded();
    await shot("05-settings-decorate");
  });

  await test.step("읽어 주기 목소리: 고르면 저장 · 미리 듣기는 앱에 든 짧은 녹음(유료 호출 없음)", async () => {
    await group("말 걸기");
    const voices = page.getByRole("group", { name: "읽어 주기 목소리" });
    await expect(voices.getByRole("button", { name: "따뜻한" })).toHaveAttribute("aria-pressed", "true");   // 기본 = 예전 목소리
    await voices.getByRole("button", { name: "차분한" }).click();
    await expect(voices.getByRole("button", { name: "차분한" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("status")).toHaveText("저장했어요.");
    const heard = page.waitForRequest(/\/voices\/matilda\.mp3$/);
    await page.getByRole("button", { name: "차분한 목소리 미리 듣기" }).click();
    await heard;
    await shot("06-settings-voice");
  });

  await test.step("우주 넓히기: 처음 나온 작은 별 · 사람을 별지기가 알려 줌", async () => {
    await nav("우주");
    await page.getByRole("group", { name: "우주 도구" }).getByRole("button", { name: "기록 목록" }).click();   // 우주 위 떠 있는 단추(2026-10-28)
    await page.getByRole("button", { name: "7/18 가족 여행 2일차" }).click();
    await page.getByTestId("planet-card").getByRole("link", { name: "정리한 결과 보기" }).click();
    const grew = page.getByTestId("universe-grew");
    await expect(grew).toContainText("이 글로 우주가 넓어졌어요. 새 작은 별 「가족」, 처음 나온 사람 지은 · 엄마.");
    await expect(grew).not.toContainText("새 해");                                          // 관계 해는 3/27 글이 먼저
    await expect(grew.locator(".who")).toHaveCSS("background-image", /\/keeper\/cat\.svg/);   // 고른 모습이 결과 카드에도
    await grew.scrollIntoViewIfNeeded();
    await shot("06-universe-grew");
    await grew.getByRole("link", { name: "우주에서 보기" }).click();
    await expect(page).toHaveURL(/\/universe$/);
    await page.getByRole("group", { name: "우주 도구" }).getByRole("button", { name: "기록 목록" }).click();   // 우주 위 떠 있는 단추(2026-10-28)
    await page.getByRole("button", { name: "8/28 막막함" }).click();
    await page.getByTestId("planet-card").getByRole("link", { name: "정리한 결과 보기" }).click();
    await expect(page.getByTestId("result")).toBeVisible();
    await expect(page.getByTestId("universe-grew")).toHaveCount(0);                         // 새로 생긴 것이 없으면 말하지 않음
  });

  expect(errors).toEqual([]);
});
