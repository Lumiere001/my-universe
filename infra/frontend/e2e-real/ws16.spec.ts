// WS16 우주 고치기 — 실제 화면 + 로컬 백엔드 + 로컬 Supabase(시험용 계정 ws16@ · 가상 인물 하늘 데모 우주) 캡처.
// 유료 호출 0: Upstage 를 가짜로 바꾼 백엔드(scripts/dev_fake_upstage.py)에서만 돈다(WS16_FAKE_UPSTAGE=1).
// 계정을 고치는 시험이라 기기마다 하늘 데모 우주를 새로 넣고 돈다(다른 갈래가 쓰는 tester@ 는 건드리지 않음):
//   uv run --frozen python -c "from app.core import config, seed; from app.repository import PgRepo; \
//     seed.demo(PgRepo(config.DATABASE_URL), seed.admin_user('ws16@my-universe.test', seed._read(seed.ENV_LOCAL)['DEV_TEST_PASSWORD']))"
//   FRONTEND_ORIGIN=http://localhost:3016 uv run --frozen python scripts/dev_fake_upstage.py 8016
//   WS16_FAKE_UPSTAGE=1 E2E_PORT=3016 NEXT_PUBLIC_API_BASE=http://localhost:8016 npx playwright test -c playwright.real.config.ts e2e-real/ws16.spec.ts --project=pc
// 캡처는 docs/screens/ws16/<기기>-NN-이름.png
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(__dirname, "../../..");
const OUT = path.join(ROOT, "docs/screens/ws16");
const env = (f: string) => Object.fromEntries(fs.readFileSync(f, "utf8").split("\n").filter((l) => /^[A-Z_]+=/.test(l))
  .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1).trim()]));
const FE = env(path.join(__dirname, "../.env.local"));
const API = process.env.NEXT_PUBLIC_API_BASE || FE.NEXT_PUBLIC_API_BASE;
const EMAIL = "ws16@my-universe.test";
const PASSWORD = env(path.join(ROOT, ".env.local")).DEV_TEST_PASSWORD; // 값은 출력하지 않는다

test.skip(!process.env.WS16_FAKE_UPSTAGE, "유료 호출을 막으려고 가짜 Upstage 백엔드(scripts/dev_fake_upstage.py)에서만 돈다");

let TOKEN = "";
type Uni = { suns: { id: string; name: string; planet_count: number }[]; stars: { id: string; sun_id: string; name: string; planet_count: number }[];
  planets: { id: string; star_id: string; sun_id: string; title: string }[] };
async function call<T>(method: string, p: string): Promise<T> {
  const r = await fetch(API + p, { method, headers: { Authorization: `Bearer ${TOKEN}` } });
  if (!r.ok) throw new Error(`${method} ${p} → ${r.status}`);
  return (await r.json()) as T;
}

test.beforeAll(async () => {
  const r = await fetch(`${FE.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST", headers: { apikey: FE.NEXT_PUBLIC_SUPABASE_ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }) });
  TOKEN = (await r.json()).access_token;
  expect(TOKEN, "시험용 계정 토큰").toBeTruthy();
});

test("우주 고치기(실제 화면 · 로컬 백엔드)", async ({ page }, info) => {
  const dev = info.project.name;
  if (dev === "mobile") await page.setViewportSize({ width: 375, height: 812 });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const shot = (name: string, full = false) => page.screenshot({ path: `${OUT}/${dev}-${name}.png`, fullPage: full, scale: "css",
    style: full ? ".top { position: static !important; } .top .nav { visibility: hidden; }" : undefined });
  const panel = page.getByTestId("edit-panel");
  const toast = panel.getByRole("status");
  const sunLabel = (name: string) => page.locator(".uni .lab.sun", { hasText: name });

  await test.step("로그인 → 우주 → 우주 고치기 펼치기", async () => {
    await page.goto("/");
    const form = page.getByRole("form", { name: "시험용 계정 로그인" });
    await form.getByLabel("이메일").fill(EMAIL);
    await form.getByLabel("비밀번호").fill(PASSWORD);
    await form.getByRole("button", { name: "시험용 계정으로 들어가기" }).click();
    await expect(page.getByRole("navigation", { name: "화면" })).toBeVisible();
    await page.goto("/universe");
    await expect(page.locator(".uni canvas")).toBeVisible();
    await panel.locator("summary").click();
    await expect(panel.getByRole("region", { name: "작은 별 옮기기" })).toBeVisible();
  });

  await test.step("해 추가 → AI 가 기준 축 제안 → 우주에 새 해가 뜸 → 축 바꾸기", async () => {
    await panel.getByLabel("새 해 이름").fill("통일 사역");
    await panel.getByRole("button", { name: "해 추가" }).click();
    await expect(toast).toContainText("“통일 사역” 해를 띄웠어요");
    await expect(sunLabel("통일 사역")).toHaveCount(1);
    const axis = panel.getByLabel("통일 사역의 기준 축");
    await axis.selectOption("공동체");
    await expect(toast).toContainText("공동체에 이었어요");
    await expect(axis).toHaveValue("공동체");
    await panel.scrollIntoViewIfNeeded();
    await shot("01-add-sun", true);
  });

  await test.step("작은 별을 새 해로 옮기면 행성이 따라감", async () => {
    const u = await call<Uni>("GET", "/universe");
    const mine = u.suns.find((s) => s.name === "통일 사역")!;
    const star = [...u.stars].sort((a, b) => a.planet_count - b.planet_count)[0];   // 행성이 가장 적은 별
    await panel.getByLabel(`${star.name}이(가) 도는 해`).selectOption(mine.id);
    await expect(toast).toContainText(`“${star.name}”을(를) 통일 사역 해로 옮겼어요`);
    await expect(sunLabel(`통일 사역 · ${star.planet_count}편`)).toHaveCount(1);
    const after = await call<Uni>("GET", "/universe");
    expect(after.planets.filter((p) => p.star_id === star.id).every((p) => p.sun_id === mine.id)).toBe(true);
    await shot("02-move-star");
  });

  await test.step("합치기 제안 → 따로 두기 · 합치기", async () => {
    const box = panel.getByRole("region", { name: "작은 별 합치기 제안" });
    const n = await box.getByRole("button", { name: "따로 두기" }).count();
    expect(n).toBeGreaterThan(1);
    await shot("03-merge-suggestions", true);
    await box.getByRole("button", { name: "따로 두기" }).first().click();
    await expect(toast).toContainText("다시 묻지 않아요");
    await expect(box.getByRole("button", { name: "따로 두기" })).toHaveCount(n - 1);
    const first = box.locator("div.stack").first();
    const into = (await first.getByRole("button").first().textContent())!.replace(/^“|”\(으\)로 합치기$/g, "");
    await first.getByRole("button").first().click();
    await expect(toast).toContainText(`“${into}”(으)로 합쳤어요`);
    await expect(box.getByRole("button", { name: "따로 두기" })).toHaveCount(n - 2);
  });

  await test.step("행성 카드에서 생각 종류 · 가치 고치기", async () => {
    await page.getByText("기록 목록으로 고르기").click();
    await page.locator("details.card", { hasText: "기록 목록으로 고르기" }).getByRole("button").first().click();
    const card = page.getByTestId("planet-card");
    await expect(card.locator("li").first()).toBeVisible();
    await card.getByRole("button", { name: "이 생각의 종류 · 가치 고치기" }).first().click();
    const fix = card.getByRole("form", { name: "생각 고치기" });
    await fix.getByLabel("생각 종류").selectOption("소망");
    await fix.getByLabel("가치").selectOption("성취");
    await fix.getByRole("button", { name: "저장" }).click();
    await expect(card.locator("li").first()).toContainText("소망");
    await expect(card.locator("li").first()).toContainText("가치 · 성취");
    await shot("04-fix-thought");
  });

  await test.step("사람 지우기 + 그 사람이 나온 생각도 지우기", async () => {
    await page.getByRole("navigation", { name: "화면" }).getByRole("link", { name: "사람", exact: true }).click();
    const who = dev === "mobile" ? "지은" : "민수";
    await page.getByRole("button", { name: `${who} 지우기` }).click();
    const dlg = page.getByRole("alertdialog", { name: `${who} 지우기 확인` });
    await dlg.getByLabel("그 사람이 나온 생각도 지우기").check();
    await expect(dlg).toContainText("우주에서 지워요");
    await shot("05-people-delete-with-thoughts");
    await dlg.getByRole("button", { name: "지우기" }).click();
    await expect(page.getByRole("status")).toContainText(/생각 \d+개를 지웠어요/);
  });

  expect(errors).toEqual([]);
});
