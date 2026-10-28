// 실제 모드 핵심 흐름(시험용 계정 tester@ · 하늘 데모 우주): 로그인 → 우주 → 지난 기록 → 새 일기(실제 Studio + Solar)
// → 진행 단계 → (휴대폰: 처리 중 새로고침 → 이어서 하기) → 결과 카드 → 피드백 · 버튼 저장 확인 → 위기 글(평소 결과 + 안부 한 줄, 유료)
// → 사람 → 되고 싶은 모습
// → 설정(팩폭) → 로그아웃. 만든 기록 · 사람 · 설정은 끝나고 되돌린다. 캡처는 docs/images/v8-real/<기기>-NN-이름.png
import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(__dirname, "../../..");
const OUT = path.join(ROOT, process.env.REAL_OUT || "docs/images/v8-real");
// REAL_SHOTS="mobile-10-result,pc-02-universe": 이 캡처만 파일로 남긴다(검사는 그대로). REAL_DIARY=mobile: 그 기기만 유료 일기를 쓴다
const KEEP = process.env.REAL_SHOTS?.split(",");
const env = (f: string) => Object.fromEntries(fs.readFileSync(f, "utf8").split("\n").filter((l) => /^[A-Z_]+=/.test(l))
  .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1).trim()]));
const FE = env(path.join(__dirname, "../.env.local"));
const API = FE.NEXT_PUBLIC_API_BASE || "http://localhost:8001";
const EMAIL = "tester@my-universe.test";
const PASSWORD = env(path.join(ROOT, ".env.local")).DEV_TEST_PASSWORD; // 값은 출력하지 않는다

// 가상 인물 '도윤'의 지어낸 글(사람 이름 1개: 서윤)
const DIARY = `10/8 목요일 밤
오늘 도서관에서 서윤이랑 조별 발표 자료를 같이 만들었다. 내가 맡은 그래프 부분을 다 못 끝내서 서윤이가 한참 기다려 줬는데 좀 미안했다.
예전에는 남한테 기대면 안 되고 혼자 다 해야 한다고 생각했는데, 오늘은 같이 나누니까 오히려 마음이 가벼웠다.
내일은 아침 수업 전에 내 몫을 먼저 끝내 두겠다.`;
const CRISIS = "요즘 너무 지쳐서 다 끝내고 싶다는 생각이 자꾸 든다.";
// 시험 단계(2026-10-08 동규): 위기 글이어도 화면에 단체 이름 · 전화번호가 나오지 않는다
const HOTLINE = /(?<!\d)(?:109|112|119)(?!\d)|마들랜|상담 ?전화/;

let TOKEN = "";
async function call<T = any>(method: string, p: string, body?: unknown): Promise<T> { // eslint-disable-line @typescript-eslint/no-explicit-any
  const r = await fetch(API + p, { method, headers: { Authorization: `Bearer ${TOKEN}`, ...(body !== undefined && { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) throw new Error(`${method} ${p} → ${r.status}`);
  return (r.status === 204 ? null : await r.json()) as T;
}
const sql = (q: string) => execFileSync("docker", ["exec", "supabase_db_my-universe", "psql", "-U", "postgres", "-tAc", q], { encoding: "utf8" }).trim();
const log = (...a: unknown[]) => console.log("결과:", ...a);

let peopleBefore: string[] = [];
const made: string[] = [];

test.beforeAll(async () => {
  const r = await fetch(`${FE.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST", headers: { apikey: FE.NEXT_PUBLIC_SUPABASE_ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }) });
  TOKEN = (await r.json()).access_token;
  expect(TOKEN, "시험용 계정 토큰").toBeTruthy();
  await call("PATCH", "/settings", { tone: "다정하게", fact_bomb_ack: false }); // 팩폭 경고를 다시 보려고
  peopleBefore = (await call("GET", "/people")).people.map((p: { id: string }) => p.id);
});

test.afterAll(async () => {
  for (const id of made) await call("DELETE", `/diary/${id}`).catch((e) => log("지우기 실패", id, String(e)));
  for (const p of (await call("GET", "/people")).people) if (!peopleBefore.includes(p.id)) await call("DELETE", `/people/${p.id}`);
  await call("PATCH", "/settings", { tone: "다정하게", fact_bomb_ack: false });
});

// 화면 글에 원시 값 · 영어 오류가 새지 않았는지
async function clean(page: Page) {
  const t = await page.locator("body").innerText();
  expect(t, "원시 값 · 영어 오류 노출").not.toMatch(/undefined|\bnull\b|NaN|\[object|\{"|Error|Failed|fetch|Internal Server/);
  expect(t, "따옴표 겹침").not.toMatch(/“["“]|["”]”/);
}

test("실제 모드 핵심 흐름", async ({ page }, info) => {
  const dev = info.project.name, touch = !!info.project.use.hasTouch;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  const shot = async (name: string, full = false) => {
    await clean(page);
    // 파일을 작게: CSS 픽셀 크기로. 전체 캡처에서는 고정 막대가 가운데 찍히지 않게 감춘다
    if (KEEP && !KEEP.includes(`${dev}-${name}`)) return;
    await page.screenshot({ path: `${OUT}/${dev}-${name}.png`, fullPage: full, scale: "css",
      style: full ? ".top { position: static !important; } .top .nav { visibility: hidden; }" : undefined });
  };
  const nav = (name: string) => page.getByRole("navigation", { name: "메뉴", exact: true }).getByRole("link", { name, exact: true }).click();
  const tapAt = async (id: string) => {
    const { x, y } = await page.evaluate((i) => (window as unknown as { __uni: { xy: (i: string) => { x: number; y: number } } }).__uni.xy(i), id);
    if (touch) await page.touchscreen.tap(x, y); else await page.mouse.click(x, y);
  };
  const uni = await call("GET", "/universe");

  await test.step("로그인(시험용 계정)", async () => {
    await page.goto("/");
    const form = page.getByRole("form", { name: "시험용 계정 로그인" });
    await form.getByLabel("이메일").fill(EMAIL);
    await form.getByLabel("비밀번호").fill(PASSWORD);
    await shot("01-login");
    await form.getByRole("button", { name: "시험용 계정으로 들어가기" }).click();
    await expect(page.getByRole("navigation", { name: "메뉴", exact: true })).toBeVisible();
  });

  await test.step("우주: 해 · 작은 별 · 행성 · 선 · 북극성", async () => {
    await nav("우주");
    await expect(page.locator(".uni canvas")).toBeVisible();
    await expect(page.locator(".uni .lab.sun")).toHaveCount(uni.suns.length);
    await expect(page.locator(".uni .lab.star")).toHaveCount(uni.stars.length);
    if (uni.north_star) await expect(page.locator(".uni .lab.north")).toHaveCount(1);
    await page.waitForTimeout(800);
    await shot("02-universe");
    log(dev, "우주", { 해: uni.suns.length, 작은별: uni.stars.length, 행성: uni.planets.length, 선: uni.links.length, 쌍행성: uni.twins.length, 북극성: !!uni.north_star });
  });

  await test.step("행성 누르기 → 요약 카드", async () => {
    // 선이 가장 많은 행성
    const deg = (id: string) => uni.links.filter((l: { from_planet: string; to_planet: string }) => l.from_planet === id || l.to_planet === id).length;
    const p = [...uni.planets].sort((a, b) => deg(b.id) - deg(a.id))[0];
    await tapAt(p.id);
    const card = page.getByTestId("planet-card");
    let how = "3D 누르기";
    if (!(await card.isVisible().catch(() => false))) {
      await page.waitForTimeout(500);
      if (!(await card.isVisible())) {
        how = "기록 목록";
        await page.getByText("목록에서 기록 고르기").click();
        await page.getByRole("button", { name: p.title, exact: true }).first().click();
      }
    }
    await expect(card).toContainText(p.title);
    await expect(card.getByText("불러오는 중…")).toHaveCount(0, { timeout: 10_000 });
    await page.waitForTimeout(300);
    await shot("03-planet");
    log(dev, "행성", how, "선", deg(p.id));
    await card.getByRole("button", { name: "닫기" }).click();
  });

  await test.step("사람 고르기 → 그 사람이 나온 행성이 빛남", async () => {
    const group = page.getByRole("group", { name: "사람 고르기" });
    for (const p of uni.people as { name: string; planets: string[] }[]) {
      const who = group.getByRole("button", { name: new RegExp(`^${p.name}`) });
      await who.click();
      await expect(who).toHaveAttribute("aria-pressed", "true");
      expect(p.planets.length, `${p.name} 이 나온 행성`).toBeGreaterThan(0);
      await expect(group.getByText("이 사람이 나온 기록이 아직 없어요")).toHaveCount(0);
      await page.waitForTimeout(300);
      if (p === uni.people[0]) await shot("04-person");
      log(dev, "사람", p.name, "빛나는 행성", p.planets.length);
      await who.click();
    }
  });

  await test.step("지난 기록", async () => {
    await nav("지난 기록");
    const items = page.locator("main .hist-list button.file");
    await expect(items.first()).toBeVisible();
    log(dev, "지난 기록 첫 쪽", await items.count());
    await shot("05-history");
    await items.first().click();
    await expect(page.getByTestId("result")).toBeVisible();
    await shot("06-history-entry");
    await page.getByRole("button", { name: "← 목록으로 돌아가기" }).click();
  });

  let entryId = "";
  const diary = !process.env.REAL_DIARY || process.env.REAL_DIARY === dev;
  if (diary) await test.step("새 일기 → 진행 단계가 실제로 바뀜", async () => {
    await nav("직접 쓰기");
    await page.getByLabel(/마음껏 적어/).fill(DIARY);
    await shot("07-write");
    const t0 = Date.now();
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    const steps = page.locator(".steps li");
    await expect(steps.first()).toBeVisible({ timeout: 30_000 });
    await expect(steps.nth(1)).toBeVisible({ timeout: 120_000 }); // 둘째 단계가 와야 '바뀐다'
    log(dev, "진행 단계(처음 둘)", await steps.allInnerTexts(), Math.round((Date.now() - t0) / 1000) + "초");
    await shot("08-progress");
    entryId = await page.evaluate(() => sessionStorage.getItem("pending-entry") ?? "");
    expect(entryId, "정리 중 기록 id").toMatch(/^e_/);
    made.push(entryId);

    if (touch) { // 휴대폰: 처리 중에 새로고침 → '이어서 하기'
      await page.reload();
      const resume = page.getByRole("button", { name: "이어서 하기" });
      await expect(resume.or(page.getByTestId("result"))).toBeVisible({ timeout: 30_000 });
      if (await resume.isVisible()) {
        await shot("09-resume");
        await resume.click();
        log(dev, "새로고침 뒤 이어서 하기", "보임 → 누름");
      } else log(dev, "새로고침 뒤", "이미 끝나 결과가 바로 나옴");
    }
    await expect(page.getByTestId("result")).toBeVisible({ timeout: 240_000 });
    log(dev, "결과까지", Math.round((Date.now() - t0) / 1000) + "초", "끝난 단계", await steps.allInnerTexts().catch(() => []));
  });

  if (diary) await test.step("결과 카드", async () => {
    const r = page.getByTestId("result");
    await expect(r.getByRole("region", { name: "별지기 한마디" })).toBeVisible();
    await expect(r.getByRole("region", { name: "생각 목록" })).toBeVisible();
    const e = await call("GET", `/diary/${entryId}`);
    log(dev, "결과", { 생각: e.thoughts.length, 종류: e.thoughts.map((t: { kind: string }) => t.kind), 관계: e.relations.length,
      점선확인: e.relations.filter((x: { needs_confirm: boolean }) => x.needs_confirm).length, 지난생각: e.past.length,
      다짐: e.thoughts.filter((t: { state: { type: string } | null }) => t.state?.type === "다짐").length, 닿은순간: e.reached.length,
      이름질문: e.people_questions.length, 다음질문: e.next_question?.kind, 말투: e.message?.tone });
    if (e.relations.length) await expect(r.getByRole("region", { name: "이어진 지난 생각" })).toBeVisible();
    // 점선(needs_confirm=true)마다 맞아요/아니에요가 떠야 한다
    await expect(r.getByRole("group", { name: "이 연결이 맞나요" })).toHaveCount(e.relations.filter((x: { needs_confirm: boolean }) => x.needs_confirm).length);
    await shot("10-result", true);
  });

  if (diary) await test.step("피드백 · 버튼 → 저장 확인", async () => {
    const r = page.getByTestId("result");
    await r.getByRole("group", { name: "한마디 피드백" }).getByRole("button", { name: "좋아요" }).click();
    await expect(r.getByRole("group", { name: "한마디 피드백" }).getByText("고마워요")).toBeVisible();
    const pressed: string[] = ["좋아요"];
    const rel = r.getByRole("group", { name: "이 연결이 맞나요" });
    if (await rel.count()) { await rel.first().getByRole("button", { name: "맞아요" }).click(); await expect(rel.first().getByText("고마워요")).toBeVisible(); pressed.push("맞아요"); }
    const vow = r.getByRole("group", { name: "다짐 상태" });
    if (await vow.count()) { await vow.first().getByRole("button", { name: "지켰어요" }).click(); await expect(r.getByText("다짐 지켰어요").first()).toBeVisible(); pressed.push("지켰어요"); }
    await r.getByRole("textbox", { name: "불편한 점 한 줄" }).fill("생각을 조금 더 크게 묶어 주면 좋겠어요");
    await r.getByRole("button", { name: "보내기" }).click();
    await expect(r.getByText("불편한 점을 받았어요")).toBeVisible();
    pressed.push("불편한 점 한 줄");
    await shot("11-feedback", true);

    // 백엔드에 남았는지: feedback 표 + 다시 불러온 결과
    const thoughtIds = (await call("GET", `/diary/${entryId}`)).thoughts.map((t: { id: string }) => t.id);
    const saved = sql(`select value from feedback where target_id = '${entryId}' or target_id like '${entryId}-%' or target_id like '%>${entryId}-%'`).split("\n").filter(Boolean);
    log(dev, "누른 것", pressed, "feedback 표", saved);
    for (const v of pressed) expect(saved, "feedback 표에 " + v).toContain(v);
    if (pressed.includes("지켰어요")) {
      await nav("지난 기록");
      await page.locator("main .hist-list button.file").first().click();
      await expect(page.getByTestId("result").getByText("다짐 지켰어요").first()).toBeVisible();
      await expect(page.getByRole("group", { name: "다짐 상태" })).toHaveCount(0);
      await shot("12-reloaded");
      log(dev, "다시 불러온 다짐", "지켜짐(버튼 없음)", thoughtIds.length);
    }
  });

  // 위기 글도 평소처럼 Studio · Solar 를 거친다(유료) → 유료 일기를 쓰는 기기에서만
  if (diary) await test.step("위기 글 → 평소 결과 카드 + 안부 한 줄(단체 안내 · 따로 뜨는 화면 없음)", async () => {
    await nav("직접 쓰기");
    await page.getByLabel(/마음껏 적어/).fill(CRISIS);
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    const r = page.getByTestId("result");
    await expect(r).toBeVisible({ timeout: 240_000 });
    await expect(r.getByTestId("check-in")).toBeVisible();
    await expect(page.locator('a[href^="tel:"]')).toHaveCount(0);
    expect(await page.locator("body").innerText(), "단체 이름 · 전화번호").not.toMatch(HOTLINE);
    const id = (await call("GET", "/diary?limit=1")).entries[0].id;
    made.push(id);
    const e = await call("GET", `/diary/${id}`);
    const calls = sql(`select coalesce(sum(calls), 0) from runs where entry_id = '${id}'`);
    log(dev, "위기 글", { 감지: e.crisis, 모드: e.message?.mode, 말투: e.message?.tone, 생각: e.thoughts.length, 외부호출: calls });
    expect(e.crisis, "감지 결과는 계속 남김").toBe(true);
    expect(e.message.mode).toBe("comfort");
    expect("care" in e, "care 칸 없음").toBe(false);
    await shot("13-crisis", true);
  });

  await test.step("사람 목록: 추가 · 지우기 안내", async () => {
    await nav("사람");
    await page.getByRole("button", { name: "사람 추가하기" }).click();
    const f = page.getByRole("form", { name: "사람 추가" });
    await f.getByLabel("이름").fill("하린");
    await f.getByLabel("나와의 관계").fill("친구");
    await f.getByRole("button", { name: "사람 추가" }).click();
    await expect(page.getByText("하린을(를) 추가했어요.")).toBeVisible();
    await expect(page.getByRole("region", { name: "하린" })).toBeVisible();
    log(dev, "사람 목록", await page.locator("main section.card[aria-label]").count(), "명");
    await shot("14-people", true);
    await page.getByRole("button", { name: "하린 지우기" }).click();
    const dlg = page.getByRole("alertdialog", { name: "하린 지우기 확인" });
    await expect(dlg).toContainText("관계 말 “친구”");
    await shot("15-people-delete");
    await dlg.getByRole("button", { name: "지우기" }).click();
    await expect(page.getByText(/하린을\(를\) 지웠어요/)).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: "사람 목록" })).toBeVisible();
    await expect(page.getByRole("region", { name: "하린" })).toHaveCount(0);
  });

  await test.step("되고 싶은 모습 4단계 저장", async () => {
    await nav("되고 싶은 모습");
    await page.getByRole("button", { name: /새로 적기|적어 보기/ }).click();
    const want = touch ? "같이 나누면서도 내 몫은 먼저 끝내는 사람" : "도움을 청할 줄 알고, 맡은 일은 끝까지 하는 사람";
    const answers = ["혼자 다 하려다 미루는 사람", want, "남한테 기대면 안 된다는 생각", "도움이 필요하면 먼저 한 줄로 말하겠다"];
    for (const [i, a] of answers.entries()) {
      await page.locator("#asp").fill(a);
      if (i === 3) await shot("16-aspiration-form");
      await page.getByRole("button", { name: "다음", exact: true }).click();
    }
    await page.getByRole("button", { name: "성취" }).click();
    await page.getByRole("button", { name: "북극성으로 띄우기" }).click();
    await expect(page.getByText("북극성으로 띄웠어요")).toBeVisible();
    await page.reload();
    await expect(page.getByRole("region", { name: "지금의 북극성" })).toContainText(want);
    await shot("17-aspiration-saved");
  });

  await test.step("설정: 팩폭 경고 뒤 선택 → 새로고침 뒤 유지", async () => {
    await nav("설정");
    await page.getByRole("button", { name: /^팩폭/ }).click();
    const w = page.getByTestId("fact-bomb-warning");
    await expect(w).toBeVisible();
    await expect(page.getByRole("button", { name: /^팩폭/ })).toHaveAttribute("aria-pressed", "false");
    await shot("18-fact-bomb-warning", true);
    await w.getByRole("button", { name: /팩폭으로 할게요/ }).click();
    await expect(page.getByRole("button", { name: /^팩폭/ })).toHaveAttribute("aria-pressed", "true");
    await page.reload();
    await expect(page.getByRole("button", { name: /^팩폭/ })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("fact-bomb-warning")).toHaveCount(0);
    // 계정 지우기 단추는 보이기만 확인(누르지 않는다 — tester@ 는 지우지 않는다)
    const del = page.getByRole("region", { name: "계정 지우기" });
    await expect(del.getByRole("button", { name: "계정과 모든 기록 지우기" })).toBeVisible();
    await expect(del.getByRole("button", { name: "계정과 모든 기록 지우기" })).toBeDisabled();
    await shot("19-settings-kept", true);
  });

  await test.step("로그아웃", async () => {
    await page.getByRole("button", { name: "로그아웃" }).click();
    await expect(page.getByRole("form", { name: "시험용 계정 로그인" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "메뉴", exact: true })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("form", { name: "시험용 계정 로그인" })).toBeVisible();
    await shot("20-logout");
  });

  expect(errors, "화면 오류가 없어야 함").toEqual([]);
});
