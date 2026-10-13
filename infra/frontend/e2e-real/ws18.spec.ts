// WS18 사진(손글씨) 입력 — 실제 화면 + 로컬 백엔드 + 로컬 Supabase(시험용 계정 tester@) + 실제 Upstage 글자 읽기(유료, 쪽당 $0.0015).
// Studio · Solar 는 가짜(scripts/dev_fake_upstage.py)라 정리 결과는 가짜다. 글자 읽기만 진짜(httpx 로 바로 부름).
//   FRONTEND_ORIGIN=http://localhost:3018 uv run --frozen python scripts/dev_fake_upstage.py 8018
//   WS18_REAL_OCR=1 E2E_PORT=3018 NEXT_PUBLIC_API_BASE=http://localhost:8018 npx playwright test -c playwright.real.config.ts e2e-real/ws18.spec.ts
// 기기마다 글자 읽기 3번(두 쪽 + 큰 사진). 돌린 뒤 runs/cost_ledger.jsonl 에 한 줄 적는다. 사진은 가상 손글씨(지호, 지어낸 글).
// 캡처는 docs/screens/ws18/<기기>-NN-이름.png(휴대폰 375 · PC 1440). 만든 기록은 지운다.
import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const ROOT = path.resolve(__dirname, "../../..");
const OUT = path.join(ROOT, "docs/screens/ws18");
const PHOTOS = path.join(ROOT, "tests/fixtures/photos");
const env = (f: string) => Object.fromEntries(fs.readFileSync(f, "utf8").split("\n").filter((l) => /^[A-Z_]+=/.test(l))
  .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1).trim()]));
const FE = env(path.join(__dirname, "../.env.local"));
const API = process.env.NEXT_PUBLIC_API_BASE || FE.NEXT_PUBLIC_API_BASE;
const EMAIL = "tester@my-universe.test";
const PASSWORD = env(path.join(ROOT, ".env.local")).DEV_TEST_PASSWORD; // 값은 출력하지 않는다

test.skip(!process.env.WS18_REAL_OCR, "유료(글자 읽기) — WS18_REAL_OCR=1 일 때만, 가짜 Upstage 백엔드(scripts/dev_fake_upstage.py)에 붙여 돈다");

// 휴대폰 원본처럼 큰 사진: 4000x3000 PNG(잡음이라 압축이 안 돼 약 36MB). 화면이 4MB 아래 JPEG 로 줄여 보내야 서버(4.5MB)를 지난다.
function bigPng(w = 4000, h = 3000): Buffer {
  const crc = (b: Buffer) => { let c = ~0; for (const x of b) { c ^= x; for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1)); } return ~c >>> 0; };
  const chunk = (type: string, data: Buffer) => {
    const t = Buffer.concat([Buffer.from(type), data]), len = Buffer.alloc(4), sum = Buffer.alloc(4);
    len.writeUInt32BE(data.length); sum.writeUInt32BE(crc(t));
    return Buffer.concat([len, t, sum]);
  };
  const head = Buffer.alloc(13);
  head.writeUInt32BE(w, 0); head.writeUInt32BE(h, 4); head[8] = 8; head[9] = 2;
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let i = 0; i < raw.length; i++) raw[i] = i % (w * 3 + 1) === 0 ? 0 : Math.imul(i, 2654435761) >>> 24;
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), chunk("IHDR", head),
    chunk("IDAT", zlib.deflateSync(raw, { level: 1 })), chunk("IEND", Buffer.alloc(0))]);
}

let TOKEN = "";
async function call<T = any>(method: string, p: string): Promise<T> { // eslint-disable-line @typescript-eslint/no-explicit-any
  const r = await fetch(API + p, { method, headers: { Authorization: `Bearer ${TOKEN}` } });
  if (!r.ok) throw new Error(`${method} ${p} → ${r.status}`);
  return (r.status === 204 ? null : await r.json()) as T;
}
let before: string[] = [];

test.beforeAll(async () => {
  const r = await fetch(`${FE.NEXT_PUBLIC_SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST", headers: { apikey: FE.NEXT_PUBLIC_SUPABASE_ANON_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }) });
  TOKEN = (await r.json()).access_token;
  expect(TOKEN, "시험용 계정 토큰").toBeTruthy();
  before = (await call("GET", "/diary?limit=100")).entries.map((e: { id: string }) => e.id);
  fs.mkdirSync(OUT, { recursive: true });
});

test.afterAll(async () => {
  for (const e of (await call("GET", "/diary?limit=100")).entries) if (!before.includes(e.id)) await call("DELETE", `/diary/${e.id}`);
});

test("사진으로 쓰기(실제 글자 읽기 · 로컬 백엔드)", async ({ page }, info) => {
  const dev = info.project.name;
  if (dev === "mobile") await page.setViewportSize({ width: 375, height: 812 });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // 보낸 사진의 형식 · 크기(브라우저가 Blob 본문을 네트워크 기록에 안 남겨서 fetch 를 감싸 잰다)
  await page.addInitScript(() => {
    const w = window as unknown as { fetch: typeof fetch; __sent: { type: string; size: number }[] }, f = w.fetch.bind(window);
    w.__sent = [];
    w.fetch = (u, o) => { if (String(u).endsWith("/photo/read") && o?.body instanceof Blob) w.__sent.push({ type: o.body.type, size: o.body.size }); return f(u, o); };
  });
  const sentPhotos = () => page.evaluate(() => (window as unknown as { __sent: { type: string; size: number }[] }).__sent);
  const shot = (name: string, full = false) => page.screenshot({ path: `${OUT}/${dev}-${name}.png`, fullPage: full, scale: "css",
    style: full ? ".top { position: static !important; } .top .nav { visibility: hidden; }" : undefined });
  const box = page.getByRole("group", { name: "사진으로 쓰기" });
  const input = box.getByLabel(/사진에서 글자 읽기/);
  const list = box.getByRole("list", { name: "읽을 사진(쪽 순서)" });
  const diary = page.getByLabel(/마음껏 적어/);

  await test.step("로그인", async () => {
    await page.goto("/");
    const form = page.getByRole("form", { name: "시험용 계정 로그인" });
    await form.getByLabel("이메일").fill(EMAIL);
    await form.getByLabel("비밀번호").fill(PASSWORD);
    await form.getByRole("button", { name: "시험용 계정으로 들어가기" }).click();
    await expect(page.getByRole("navigation", { name: "화면" })).toBeVisible();
    await expect(diary).toBeVisible();
  });

  await test.step("형식 밖 파일 → 친절한 오류", async () => {
    await input.setInputFiles([{ name: "일기.gif", mimeType: "image/gif", buffer: Buffer.from("GIF89a") }]);
    await expect(box.getByRole("alert")).toContainText("jpg · png · heic 사진만");
    await box.scrollIntoViewIfNeeded();
    await shot("01-bad-type");
  });

  await test.step("두 쪽을 거꾸로 올림 → 순서 바꾸기 → 읽기(실제 Upstage) → 쓰기 칸에 쪽 순서대로", async () => {
    await input.setInputFiles([path.join(PHOTOS, "jiho-1012-p2.jpg"), path.join(PHOTOS, "jiho-1012-p1.jpg")]);
    await list.getByRole("button", { name: "1쪽 뒤로" }).click();
    await expect(list.getByRole("listitem").first()).toContainText("p1");
    await shot("02-two-pages");
    await box.getByRole("button", { name: "사진 2장 글자 읽기" }).click();
    await expect(box.getByRole("status")).toContainText("2쪽을 읽어 위 칸에 채웠어요", { timeout: 60_000 });
    const text = await diary.inputValue();
    expect(text.split("\n")[0]).toContain("10월 12일");
    expect(text.indexOf("서윤 선배와")).toBeGreaterThan(text.indexOf("민준이가"));   // 1쪽 → 2쪽 순서
    const sent = await sentPhotos();
    expect(sent).toHaveLength(2);
    expect(sent.every((s) => s.type === "image/jpeg" && s.size > 0 && s.size <= 4_000_000)).toBe(true);
    await diary.scrollIntoViewIfNeeded();
    await shot("03-read-filled");
  });

  await test.step("잘못 읽은 글자를 고쳐 띄움 → 사진 출처 · 글이 다루는 날 = 첫 줄 날짜(확실)", async () => {
    await diary.fill((await diary.inputValue()).replace("일람", "알람"));
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    const result = page.getByTestId("result");
    await expect(result).toBeVisible({ timeout: 60_000 });
    await expect(result.getByTestId("entry-day")).toContainText("2026-10-12");
    const e = (await call("GET", "/diary?limit=1")).entries[0];
    const full = await call("GET", `/diary/${e.id}`);
    expect([full.source, full.day, full.day_basis]).toEqual(["사진", "2026-10-12", "확실"]);
    await shot("04-result", true);
    await page.getByRole("button", { name: "새 글 쓰기" }).click();
  });

  await test.step("큰 사진(약 36MB PNG) → 화면이 4MB 아래 JPEG 로 줄여 보냄 → 읽힘", async () => {
    await input.setInputFiles([{ name: "큰사진.png", mimeType: "image/png", buffer: bigPng() }]);
    await box.getByRole("button", { name: "사진 1장 글자 읽기" }).click();
    // 잡음 사진: 글자가 없으면 안내, 잡음을 글자로 읽으면 채움(어느 쪽이든 서버 4.5MB 를 지나 읽힌 것)
    await expect(box.getByRole("alert").or(box.getByRole("status"))).toBeVisible({ timeout: 60_000 });
    const sent = await sentPhotos(), last = sent[sent.length - 1];
    expect(sent).toHaveLength(3);
    expect(last.type).toBe("image/jpeg");
    expect(last.size).toBeLessThanOrEqual(4_000_000);
    await box.scrollIntoViewIfNeeded();
    await shot("05-big-photo");
  });
  expect(errors).toEqual([]);
});
