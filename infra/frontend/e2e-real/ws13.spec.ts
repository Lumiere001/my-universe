// WS13 쓰기 화면 작은 묶음 — 실제 화면 + 로컬 백엔드 + 로컬 Supabase(시험용 계정 tester@ · 하늘 데모 우주) 캡처.
// 유료 호출 0: Upstage 를 가짜로 바꾼 백엔드(scripts/dev_fake_upstage.py)에서만 돈다(WS13_FAKE_UPSTAGE=1). 정리 결과는 가짜다.
//   FRONTEND_ORIGIN=http://localhost:3013 uv run --frozen python scripts/dev_fake_upstage.py 8013
//   WS13_FAKE_UPSTAGE=1 E2E_PORT=3013 NEXT_PUBLIC_API_BASE=http://localhost:8013 npx playwright test -c playwright.real.config.ts e2e-real/ws13.spec.ts
// 캡처는 docs/screens/ws13/<기기>-NN-이름.png(휴대폰 375 · PC 1440). 만든 기록은 지우고 설정(날씨 묻기 · 별지기 이름)은 되돌린다.
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(__dirname, "../../..");
const OUT = path.join(ROOT, "docs/screens/ws13");
const env = (f: string) => Object.fromEntries(fs.readFileSync(f, "utf8").split("\n").filter((l) => /^[A-Z_]+=/.test(l))
  .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1).trim()]));
const FE = env(path.join(__dirname, "../.env.local"));
const API = process.env.NEXT_PUBLIC_API_BASE || FE.NEXT_PUBLIC_API_BASE;
const EMAIL = "tester@my-universe.test";
const PASSWORD = env(path.join(ROOT, ".env.local")).DEV_TEST_PASSWORD; // 값은 출력하지 않는다
const ymd = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
const YESTERDAY = ymd(new Date(Date.now() - 86_400_000));
// 가상 인물 하늘의 지어낸 글
const MD = "# 9/25 독서노트 — 『작은 습관의 힘』\n\n## 읽은 것\n습관은 의지가 아니라 환경에서 시작된다는 장을 읽었다.\n## 해 볼 것\n내일부터 책상 위에 책을 펴 두겠다.";
const TXT = "저녁 산책\n저녁에 동네를 한 바퀴 걸었다. 바람이 시원해서 기분이 좋았다.";

test.skip(!process.env.WS13_FAKE_UPSTAGE, "유료 호출을 막으려고 가짜 Upstage 백엔드(scripts/dev_fake_upstage.py)에서만 돈다");

let TOKEN = "";
async function call<T = any>(method: string, p: string, body?: unknown): Promise<T> { // eslint-disable-line @typescript-eslint/no-explicit-any
  const r = await fetch(API + p, { method, headers: { Authorization: `Bearer ${TOKEN}`, ...(body !== undefined && { "Content-Type": "application/json" }) },
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) throw new Error(`${method} ${p} → ${r.status}`);
  return (r.status === 204 ? null : await r.json()) as T;
}
let before: string[] = [];
let settings: { weather_ask: boolean; keeper_name?: string } = { weather_ask: true };

test.beforeAll(async () => {
  const r = await fetch(`${FE.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST", headers: { apikey: FE.NEXT_PUBLIC_SUPABASE_ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }) });
  TOKEN = (await r.json()).access_token;
  expect(TOKEN, "시험용 계정 토큰").toBeTruthy();
  settings = (await call("GET", "/me")).settings;
  before = (await call("GET", "/diary?limit=100")).entries.map((e: { id: string }) => e.id);
  await call("PATCH", "/settings", { weather_ask: true });
});

test.afterAll(async () => {
  for (const e of (await call("GET", "/diary?limit=100")).entries) if (!before.includes(e.id)) await call("DELETE", `/diary/${e.id}`);
  await call("PATCH", "/settings", { weather_ask: settings.weather_ask, keeper_name: settings.keeper_name || "별지기" });
});

test("쓰기 화면 작은 묶음(실제 화면 · 로컬 백엔드)", async ({ page }, info) => {
  const dev = info.project.name;
  if (dev === "mobile") await page.setViewportSize({ width: 375, height: 812 });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const shot = (name: string, full = false) => page.screenshot({ path: `${OUT}/${dev}-${name}.png`, fullPage: full, scale: "css",
    style: full ? ".top { position: static !important; } .top .nav { visibility: hidden; }" : undefined });
  const nav = (name: string) => page.getByRole("navigation", { name: "메뉴", exact: true }).getByRole("link", { name, exact: true }).click();
  const bubble = page.getByRole("region", { name: "별지기 말풍선" });
  const result = page.getByTestId("result");
  const submit = () => page.getByRole("button", { name: "우주에 띄우기" }).click();
  const again = async () => { await page.getByRole("button", { name: "새 글 쓰기" }).click(); await expect(page.getByLabel(/마음껏 적어/)).toBeVisible(); };
  const file = page.getByLabel("글 파일(.txt · .md)에서 불러오기");

  await test.step("로그인 → 쓰기 화면 위 말풍선(다짐 안부)", async () => {
    await page.goto("/");
    const form = page.getByRole("form", { name: "시험용 계정 로그인" });
    await form.getByLabel("이메일").fill(EMAIL);
    await form.getByLabel("비밀번호").fill(PASSWORD);
    await form.getByRole("button", { name: "시험용 계정으로 들어가기" }).click();
    await expect(page.getByRole("navigation", { name: "메뉴", exact: true })).toBeVisible();
    await page.getByRole("navigation", { name: "메뉴", exact: true }).getByRole("link", { name: "직접 쓰기", exact: true }).click();   // 첫 화면은 이야기하기
    await expect(bubble).toBeVisible();
    await shot("01-write-bubble");
  });

  await test.step("어제 날짜 · 제목으로 쓰면 day 가 어제", async () => {
    await page.getByLabel(/제목/).fill("도서관에서 보낸 하루");
    await page.getByLabel(/글이 다루는 날/).fill(YESTERDAY);
    await page.getByLabel(/마음껏 적어/).fill("도서관에서 오래 공부했다.\n다음 주에는 한 곳이라도 먼저 메일을 보내 보겠다.");
    await shot("02-write-fields");
    await submit();
    await expect(result).toBeVisible({ timeout: 60_000 });
    await expect(result.getByTestId("entry-day")).toContainText(YESTERDAY);
    const id = (await call("GET", "/diary?limit=1")).entries[0];
    expect([id.day, id.day_basis]).toEqual([YESTERDAY, "확실"]);
    await shot("03-result-yesterday", true);
  });

  await test.step("말풍선에 지난 질문(날씨) → 건너뛰기 → 날씨 질문 없음", async () => {
    await again();
    await page.getByLabel(/마음껏 적어/).fill("오늘은 그냥 그랬다.");
    await submit();
    await expect(result).toBeVisible({ timeout: 60_000 });
    await again();
    await expect(bubble.getByTestId("prompt-question")).toContainText("마음 날씨");
    await shot("04-bubble-last-question");
    await bubble.getByRole("button", { name: "다음부터 묻지 않기" }).click();
    await expect(bubble.getByText("다음부터 마음 날씨는 묻지 않을게요")).toBeVisible();
    await shot("05-weather-skipped");
    await page.reload();
    await expect(page.getByLabel(/마음껏 적어/)).toBeVisible();
    await page.waitForTimeout(500);
    await expect(bubble.getByTestId("prompt-question")).toHaveCount(0);
    expect((await call("GET", "/diary/prompt")).kind).toBe("none");
  });

  await test.step(".md 불러오기(파일 이름 날짜 → day) → 결과", async () => {
    await file.setInputFiles({ name: "2026-09-25-독서노트.md", mimeType: "text/markdown", buffer: Buffer.from(MD) });
    await expect(page.getByLabel(/글이 다루는 날/)).toHaveValue("2026-09-25");
    await shot("06-file-loaded");
    await submit();
    await expect(result.getByTestId("entry-day")).toContainText("2026-09-25", { timeout: 60_000 });
    await shot("07-result-md", true);
  });

  await test.step(".txt 불러오기 → 결과 → 같은 파일 다시 → '이미 정리한 글이에요'", async () => {
    await again();
    await file.setInputFiles({ name: "산책.txt", mimeType: "text/plain", buffer: Buffer.from(TXT) });
    await submit();
    await expect(result.getByRole("heading", { name: "저녁 산책" })).toBeVisible({ timeout: 60_000 });
    await again();
    await file.setInputFiles({ name: "산책.txt", mimeType: "text/plain", buffer: Buffer.from(TXT) });
    await submit();
    const dup = page.getByRole("status", { name: "이미 정리한 글" });
    await expect(dup).toBeVisible({ timeout: 60_000 });
    await shot("08-duplicate");
    await dup.getByRole("link", { name: "지난 기록에서 보기" }).click();
    await expect(result.getByRole("heading", { name: "저녁 산책" })).toBeVisible();
  });

  await test.step("날짜 확인 필요 → 날짜 고르기", async () => {
    await nav("직접 쓰기");
    await page.getByLabel(/제목/).fill("3/27~3/29 제주 여행");
    await page.getByLabel(/마음껏 적어/).fill("사흘 동안 바다를 보고 왔다. 다음에는 가족과 같이 오고 싶다.");
    await submit();
    const fix = result.getByTestId("day-fix");
    await expect(fix).toBeVisible({ timeout: 60_000 });
    await fix.getByLabel("글이 다루는 날").fill("2026-03-28");
    await shot("09-day-check");
    await fix.getByRole("button", { name: "이 날로 고치기" }).click();
    await expect(result.getByTestId("entry-day")).toContainText("2026-03-28");
    await expect(result.getByTestId("day-fix")).toHaveCount(0);
  });

  await test.step("지난 기록 지우기 → 목록 · 우주에서 사라짐", async () => {
    await nav("지난 기록");
    const item = page.getByRole("button", { name: /3\/27~3\/29 제주 여행/ });
    await item.click();
    await page.getByRole("button", { name: "이 기록 지우기" }).click();
    await shot("10-delete-confirm", true);
    const id = (await call("GET", "/diary?limit=100")).entries.find((e: { title: string }) => e.title.includes("제주 여행")).id;
    await page.getByRole("alertdialog", { name: "기록 지우기 확인" }).getByRole("button", { name: "지우기" }).click();
    await expect(page.getByText("기록을 지웠어요.")).toBeVisible();
    await expect(item).toHaveCount(0);
    expect((await call("GET", "/universe")).planets.map((p: { id: string }) => p.id)).not.toContain(id);
    await nav("우주");
    await page.getByText("목록에서 기록 고르기").click();
    await expect(page.getByRole("button", { name: /제주 여행/ })).toHaveCount(0);
  });

  await test.step("별지기 이름 바꾸기", async () => {
    await nav("설정");
    await page.getByLabel("별지기 이름").fill("달지기");
    await page.getByRole("button", { name: "이름 바꾸기" }).click();
    await expect(page.getByText("저장했어요.")).toBeVisible();
    await shot("11-keeper-name");
    await nav("지난 기록");
    await page.getByRole("button", { name: /저녁 산책/ }).click();
    await expect(result.getByRole("region", { name: "별지기 한마디" })).toContainText("달지기 ·");
  });

  expect(errors, "화면 오류가 없어야 함").toEqual([]);
});
