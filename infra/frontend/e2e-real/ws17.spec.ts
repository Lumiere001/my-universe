// WS17 인스타 ZIP 가져오기 — 실제 화면 + 로컬 백엔드 + 로컬 Supabase(시험용 계정 tester@), 가상 인물 도담의 예시 ZIP(public/samples).
// 유료 호출 0: Upstage 를 가짜로 바꾼 백엔드(scripts/dev_fake_upstage.py)에서만 돈다(WS17_FAKE_UPSTAGE=1). 정리 결과는 가짜다.
//   FRONTEND_ORIGIN=http://localhost:3017 uv run --frozen python scripts/dev_fake_upstage.py 8017
//   WS17_FAKE_UPSTAGE=1 E2E_PORT=3017 NEXT_PUBLIC_API_BASE=http://localhost:8017 npx playwright test -c playwright.real.config.ts e2e-real/ws17.spec.ts
// 확인: 브라우저가 ZIP 을 풀어 글 6편(이어 쓴 게시물 묶음 · 깨진 한글 복원) · 예상 시간 · 비용을 먼저 보임 → 최근 2편만 → 2편만 기록,
// 같은 ZIP 다시 → 2편 '이미 가져옴' → 나머지 전부 시작 → 멈추기 → 이어 하기 → 끝, 새 기록은 모두 6편. 캡처는 docs/screens/ws17/.
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(__dirname, "../../..");
const OUT = path.join(ROOT, "docs/screens/ws17");
const ZIP = path.join(__dirname, "../public/samples/instagram-virtual-dodam.zip");
const env = (f: string) => Object.fromEntries(fs.readFileSync(f, "utf8").split("\n").filter((l) => /^[A-Z_]+=/.test(l))
  .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1).trim()]));
const FE = env(path.join(__dirname, "../.env.local"));
const API = process.env.NEXT_PUBLIC_API_BASE || FE.NEXT_PUBLIC_API_BASE;
const EMAIL = "tester@my-universe.test";
const PASSWORD = env(path.join(ROOT, ".env.local")).DEV_TEST_PASSWORD; // 값은 출력하지 않는다

test.skip(!process.env.WS17_FAKE_UPSTAGE, "유료 호출을 막으려고 가짜 Upstage 백엔드(scripts/dev_fake_upstage.py)에서만 돈다");

let TOKEN = "";
type Entry = { id: string; title: string; day?: string };
async function call<T = any>(method: string, p: string): Promise<T> { // eslint-disable-line @typescript-eslint/no-explicit-any
  const r = await fetch(API + p, { method, headers: { Authorization: `Bearer ${TOKEN}` } });
  if (!r.ok) throw new Error(`${method} ${p} → ${r.status}`);
  return (r.status === 204 ? null : await r.json()) as T;
}
const entries = async () => (await call<{ entries: Entry[] }>("GET", "/diary?limit=100")).entries;
let before: string[] = [];

test.beforeAll(async () => {
  const r = await fetch(`${FE.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST", headers: { apikey: FE.NEXT_PUBLIC_SUPABASE_ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }) });
  TOKEN = (await r.json()).access_token;
  expect(TOKEN, "시험용 계정 토큰").toBeTruthy();
  before = (await entries()).map((e) => e.id);
});

test.afterEach(async () => {   // 기기마다 새로 가져오게 만든 기록을 지운다
  for (const e of await entries()) if (!before.includes(e.id)) await call("DELETE", `/diary/${e.id}`);
});

test("인스타 ZIP 가져오기(실제 화면 · 로컬 백엔드)", async ({ page }, info) => {
  const dev = info.project.name;
  if (dev === "mobile") await page.setViewportSize({ width: 375, height: 812 });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const shot = (name: string, full = false) => page.screenshot({ path: `${OUT}/${dev}-${name}.png`, fullPage: full, scale: "css",
    style: full ? ".top { position: static !important; } .top .nav { visibility: hidden; }" : undefined });
  const progress = page.getByRole("region", { name: "가져오기 진행" });
  const added = async () => (await entries()).filter((e) => !before.includes(e.id));

  await test.step("로그인 → 쓰기 화면의 링크로 가져오기 화면", async () => {
    await page.goto("/");
    const form = page.getByRole("form", { name: "시험용 계정 로그인" });
    await form.getByLabel("이메일").fill(EMAIL);
    await form.getByLabel("비밀번호").fill(PASSWORD);
    await form.getByRole("button", { name: "시험용 계정으로 들어가기" }).click();
    await expect(page.getByRole("navigation", { name: "화면" })).toBeVisible();
    await page.getByRole("link", { name: "인스타그램 글 한꺼번에 가져오기" }).click();
    await expect(page.getByRole("heading", { name: "인스타그램에서 가져오기" })).toBeVisible();
    await shot("01-pick");
  });

  await test.step("ZIP 고르기 → 글 6편 · 예상 시간 · 비용", async () => {
    await page.getByLabel(/ZIP 파일/).setInputFiles(ZIP);
    await expect(page.getByRole("heading", { name: "글 6편을 찾았어요" })).toBeVisible();
    const list = page.getByRole("list", { name: "글 목록(최근 것부터)" });
    await expect(list.getByRole("listitem")).toHaveCount(6);
    await expect(list.getByRole("listitem").first()).toContainText("3/28 동아리 해커톤 (1)");   // 깨진 한글 복원 + 묶음
    await expect(list.getByRole("listitem").first()).toContainText("게시물 2개");
    await expect(list.getByRole("listitem").last()).toContainText("2025-12-31");                  // 1월에 올린 12/31 → 지난해
    await expect(page.getByText(/6편 · 예상 시간 약 6분 · 예상 비용 약 \$0\.60/)).toBeVisible();
    await shot("02-preview", true);
  });

  await test.step("최근 2편만 → 2편만 기록", async () => {
    await page.getByLabel("최근 몇 편").fill("2");
    await expect(page.getByText(/2편 · 예상 시간 약 2분 · 예상 비용 약 \$0\.20/)).toBeVisible();
    await page.getByRole("button", { name: "가져오기 시작" }).click();
    await expect(progress.getByRole("heading", { name: "다 가져왔어요" })).toBeVisible({ timeout: 120_000 });
    await expect(progress).toContainText("2 / 2편 · 새로 정리 2편");
    await shot("03-done-2", true);
    const got = await added();
    expect(got.map((e) => e.title).sort()).toEqual(["", "3/28 동아리 해커톤 (1)"]);
    const d = await call("GET", `/diary/${got.find((e) => e.title)!.id}`);
    expect([d.source, d.day, d.day_basis, d.written_at.slice(0, 16)]).toEqual(["지난 글 묶음", "2026-03-28", "확실", "2026-03-29T01:20"]);
  });

  await test.step("같은 ZIP 다시 → 2편 '이미 가져옴', 나머지 전부 → 멈추기 → 이어 하기", async () => {
    await page.reload();
    await page.getByLabel(/ZIP 파일/).setInputFiles(ZIP);
    await expect(page.getByText("이미 가져왔거나 너무 긴 글 2편은 건너뛰어요.")).toBeVisible();
    await expect(page.getByRole("list", { name: "글 목록(최근 것부터)" }).getByText("이미 가져옴")).toHaveCount(2);
    await shot("04-preview-again", true);
    await page.getByRole("radio", { name: /전부 4편/ }).check();
    // 가짜 Upstage 는 빨라서 멈추기 전에 끝날 수 있다: 글 보내기를 한 편당 1.5초 늦춘다
    await page.route("**/diary/stream", async (r) => { await new Promise((ok) => setTimeout(ok, 1500)); await r.continue(); });
    await page.getByRole("button", { name: "가져오기 시작" }).click();
    await progress.getByRole("button", { name: "멈추기" }).click();
    await expect(progress.getByRole("heading", { name: "멈췄어요" })).toBeVisible({ timeout: 120_000 });
    await shot("05-paused");
    const left = Number((await progress.getByRole("button", { name: /이어 하기/ }).textContent())!.match(/(\d+)편 남음/)![1]);
    expect(left).toBeGreaterThan(0);
    expect((await added()).length).toBe(2 + 4 - left);
    await progress.getByRole("button", { name: /이어 하기/ }).click();
    await expect(progress.getByRole("heading", { name: "다 가져왔어요" })).toBeVisible({ timeout: 120_000 });
    await expect(progress).toContainText("4 / 4편 · 새로 정리 4편");
    await shot("06-done-all", true);
    expect((await added()).length).toBe(6);   // 같은 ZIP 을 두 번 골라도 새 기록은 글 수만큼
  });

  expect(errors).toEqual([]);
});
