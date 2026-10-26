// WS26 수용 기준: 로그아웃 '/' → 소개 · '구글로 시작하기', 로그인 상태는 이야기하기 화면(2026-10-14 결정), manifest · 아이콘 · 서비스 워커 등록 · 설치 가능,
// 서비스 워커 캐시에 API 응답 · 일기 글이 없음, OG 메타, 설치 안내(안드로이드 버튼 · 아이폰 그림 · 설치했으면 숨김), 개인정보처리방침 링크.
// 데이터는 가상 인물(하늘)뿐. 캡처는 docs/screens/ws26/.
import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { FAKE } from "../playwright.landing.config";

const OUT = path.resolve(__dirname, "../../../docs/screens/ws26");
// API 응답마다 이 가상 일기 문장을 넣고, 서비스 워커 캐시 어디에도 남지 않는지 본다
const DIARY = "가상 인물 하늘: 관심 있는 팀 세 곳을 찾아보기로 했는데 또 미뤘다";
const IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";

const shot = (page: Page, name: string, full = true) => page.screenshot({ path: `${OUT}/${test.info().project.name}-${name}.png`, fullPage: full });
const b64 = (o: object) => Buffer.from(JSON.stringify(o)).toString("base64url");

// 로그인한 것처럼: supabase-js 가 읽는 저장소 열쇠에 가짜 세션(서버로 확인하지 않음)
async function signedIn(page: Page) {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  const user = { id: "00000000-0000-4000-8000-000000000001", aud: "authenticated", role: "authenticated", email: "haneul@example.test",
    app_metadata: { provider: "google" }, user_metadata: {}, created_at: "2026-10-01T00:00:00Z" };
  const jwt = `${b64({ alg: "HS256", typ: "JWT" })}.${b64({ sub: user.id, exp, aud: "authenticated", role: "authenticated", email: user.email })}.c2ln`;
  const session = { access_token: jwt, refresh_token: "fake-refresh", token_type: "bearer", expires_in: 3600, expires_at: exp, user };
  await page.addInitScript(([k, v]) => localStorage.setItem(k, v), ["sb-127-auth-token", JSON.stringify(session)]);
  const onto = JSON.parse(fs.readFileSync(path.join(__dirname, "../lib/ontology.json"), "utf8"));
  const settings = { tone: "다정하게", fact_bomb_ack: false, gentle_today: null, comfort_only_today: null, suggestions: "보통", cross_links: "눌렀을 때", weather_ask: true };
  const body: Record<string, object> = {
    "/me": { user: { id: user.id, email: user.email }, settings, onboarding: { entries: 3, aspiration: DIARY, weather_asked: true } },
    "/ontology": onto,
    "/diary": { entries: [{ id: "e1", written_at: "2026-10-03T21:00:00+09:00", title: "10/3 토요일 일기", summary: DIARY, weather: "흐림", status: "done", sun: "삶의 성취", star: "진로" }] },
    "/settings/suggestions": { suggestions: [] },   // 설정 화면의 '이 설정으로 바꿀까요?'(WS22): 제안 없음
    // 로그인 뒤 첫 화면(이야기하기)이 여는 이어 할 대화 하나(별지기가 먼저 물은 말만)
    "/talk": { conversations: [{ id: "c1", created_at: "2026-10-03T21:00:00+09:00", updated_at: "2026-10-03T21:00:00+09:00", summary: "",
      turns: [{ role: "keeper", kind: "first", text: "오늘 하루는 어땠어요?", at: "2026-10-03T21:00:00+09:00" }],
      from_entry: null, entry_id: null, turn_count: 0, wrap: false }] },
  };
  await page.route(`${FAKE.api}/**`, (r) => {
    const p = new URL(r.request().url()).pathname;
    return r.fulfill({ status: 200, headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Authorization, Content-Type",
      "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE" },
      contentType: "application/json", json: body[p] ?? { note: DIARY } });
  });
}

const pngSize = (b: Buffer) => [b.readUInt32BE(16), b.readUInt32BE(20)];
// 화면 오류 · 404 같은 콘솔 오류를 모은다(예: 아직 없는 /terms 를 Link 가 미리 받아 404)
const watchErrors = (page: Page) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`${m.text()} ${m.location().url}`); });
  return errors;
};

test("로그아웃: 소개 → 구글로 시작하기, 개인정보처리방침 링크", async ({ page }, info) => {
  fs.mkdirSync(OUT, { recursive: true });
  const errors = watchErrors(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "나의 우주" })).toBeVisible();
  await expect(page.getByRole("button", { name: "구글로 시작하기" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "쓰는 법" })).toBeVisible();
  await expect(page.locator(".how > li")).toHaveCount(3);
  await expect(page.getByRole("heading", { name: "개인정보 약속" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "시험 단계 안내" })).toBeVisible();
  await expect(page.getByRole("link", { name: "개인정보처리방침", exact: true })).toHaveAttribute("href", "/privacy");
  await expect(page.getByRole("link", { name: "이용약관" })).toHaveAttribute("href", "/terms");
  await expect(page.getByRole("navigation", { name: "메뉴", exact: true })).toHaveCount(0); // 앱 메뉴는 로그인 뒤에만
  for (const img of await page.locator(".landing img").all()) { // 캡처 그림이 모두 실제로 뜸
    await img.scrollIntoViewIfNeeded();
    await expect.poll(() => img.evaluate((e: HTMLImageElement) => e.complete && e.naturalWidth)).toBeGreaterThan(0);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, "01-landing");
  if (info.project.name === "mobile") { // 375 에서도 가로로 넘치지 않음
    await page.setViewportSize({ width: 375, height: 812 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
    await shot(page, "01-landing-375");
  }

  // 개인정보처리방침은 로그인 없이 열림
  await page.getByRole("link", { name: "개인정보처리방침 자세히 보기" }).click();
  await expect(page.getByRole("heading", { name: "나의 우주 개인정보처리방침" })).toBeVisible();
  await page.goBack();
  expect(errors, "화면 오류가 없어야 함").toEqual([]);

  // '구글로 시작하기' → Supabase 구글 로그인 주소로 간다(가짜 주소라 거기서 멈춤)
  await page.route(`${FAKE.supabase}/**`, (r) => r.fulfill({ contentType: "text/html", body: "<p>google</p>" }));
  const go = page.waitForRequest((r) => r.url().startsWith(`${FAKE.supabase}/auth/v1/authorize`));
  await page.getByRole("button", { name: "구글로 시작하기" }).first().click();
  const url = new URL((await go).url());
  expect(url.searchParams.get("provider")).toBe("google");
  expect(url.searchParams.get("redirect_to")).toBe(info.project.use.baseURL);
});

test("로그인 상태: 소개 없이 바로 이야기하기 화면", async ({ page }) => {
  const errors = watchErrors(page);
  await signedIn(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "이야기하기", level: 1 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "메뉴", exact: true, includeHidden: true })).toHaveCount(1);   // 휴대폰은 서랍 안
  await expect(page.getByRole("navigation", { name: /^(메뉴|바로 가기)$/ }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "구글로 시작하기" })).toHaveCount(0);
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "별지기 말투" })).toBeVisible();
  await expect(page.getByRole("link", { name: "이용약관" })).toHaveAttribute("href", "/terms");
  await shot(page, "03-settings");
  expect(errors, "화면 오류가 없어야 함").toEqual([]);
});

test("설치형 웹앱: manifest · 아이콘 · 서비스 워커 · 설치 가능", async ({ page, request }) => {
  await page.goto("/");
  const href = await page.locator('link[rel="manifest"]').getAttribute("href");
  expect(href).toBe("/manifest.webmanifest");
  const m = await (await request.get(href!)).json();
  expect(m).toMatchObject({ name: "나의 우주", short_name: "나의 우주", display: "standalone", start_url: "/", scope: "/", theme_color: "#1e1e1e" });
  const icons = m.icons as { src: string; sizes: string; type: string; purpose: string }[];
  for (const i of icons.filter((x) => x.type === "image/png")) {
    const r = await request.get(i.src);
    expect(r.status(), i.src).toBe(200);
    expect(pngSize(await r.body()).join("x"), i.src).toBe(i.sizes);
  }
  expect(icons.map((i) => `${i.sizes}/${i.purpose}`)).toEqual(expect.arrayContaining(["192x192/any", "512x512/any", "512x512/maskable"]));
  const apple = await page.locator('link[rel="apple-touch-icon"]').getAttribute("href");
  expect(pngSize(await (await request.get(apple!)).body()).join("x")).toBe("180x180");

  const sw = await page.evaluate(async () => (await navigator.serviceWorker.ready).active?.scriptURL);
  expect(sw).toMatch(/\/sw\.js$/);
  // 크롬이 '설치 가능'으로 보는지(옛 Lighthouse '설치 가능' 검사와 같은 판정)
  const cdp = await page.context().newCDPSession(page);
  const man = await cdp.send("Page.getAppManifest");
  expect(man.errors).toEqual([]);
  const { installabilityErrors } = await cdp.send("Page.getInstallabilityErrors");
  expect(installabilityErrors).toEqual([]);
});

test("서비스 워커 캐시에 API 응답 · 일기 글이 없음 + 오프라인 안내", async ({ page, context }) => {
  await signedIn(page);
  await page.goto("/");
  await page.evaluate(() => navigator.serviceWorker.ready);
  await page.reload(); // 이제 서비스 워커가 화면을 맡는다
  expect(await page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);
  await page.goto("/history");
  await expect(page.getByText(DIARY)).toBeVisible(); // 가짜 API 의 일기 글이 실제로 화면에 왔다
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "별지기 말투" })).toBeVisible();
  await page.goto("/privacy");

  const cached = await page.evaluate(async () => {
    const out: { url: string; body: string }[] = [];
    for (const k of await caches.keys()) {
      const c = await caches.open(k);
      for (const r of await c.keys()) out.push({ url: r.url, body: await (await c.match(r))!.text() });
    }
    return out;
  });
  expect(cached.map((c) => new URL(c.url).pathname)).toEqual(["/offline.html"]);
  for (const c of cached) {
    expect(c.url).not.toContain(FAKE.api);
    expect(c.body).not.toContain(DIARY);
  }

  await context.setOffline(true);
  await page.goto("/universe");
  await expect(page.getByRole("heading", { name: "인터넷에 연결되어 있지 않아요" })).toBeVisible();
  await shot(page, "04-offline", false);
  await context.setOffline(false);
});

test("공유 미리보기 · 검색: OG 메타, robots · sitemap, 로그인 뒤 화면 noindex", async ({ request }) => {
  const html = await (await request.get("/")).text();
  for (const p of ["og:title", "og:description", "og:image", "twitter:card", "twitter:image"])
    expect(html, p).toMatch(new RegExp(`(property|name)="${p}" content="[^"]+"`));
  const og = html.match(/property="og:image" content="([^"]+)"/)![1];
  expect(new URL(og).pathname).toBe("/og.jpg");
  expect((await request.get("/og.jpg")).status()).toBe(200);
  expect(await (await request.get("/robots.txt")).text()).toContain("Sitemap:");
  const map = await (await request.get("/sitemap.xml")).text();
  expect([...map.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => new URL(m[1]).pathname)).toEqual(["/", "/privacy"]);
  for (const p of ["/", "/privacy"]) expect((await request.get(p)).headers()["x-robots-tag"], p).toBeUndefined();
  for (const p of ["/universe", "/history", "/people", "/aspiration", "/settings"]) expect((await request.get(p)).headers()["x-robots-tag"], p).toBe("noindex");
  for (const p of ["/og.jpg", "/manifest.webmanifest", "/sw.js", "/icons/icon-512.png"]) expect((await request.get(p)).headers()["x-robots-tag"], p).toBeUndefined();
});

test("설치 안내: 안드로이드 '앱 설치' 버튼 · 아이폰 그림 안내 · 설치했으면 숨김", async ({ page, browser }, info) => {
  // 크롬: beforeinstallprompt 가 오면 '앱 설치' 버튼(헤드리스에서는 직접 보내 흉내)
  await page.goto("/");
  const guide = page.getByRole("region", { name: "앱으로 설치" });
  await expect(async () => { // 소개 화면이 뜬 뒤(듣기 시작한 뒤)에 보내야 받으므로 보일 때까지 다시 보낸다
    await page.evaluate(() => {
      const e = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), {
        prompt: async () => { (window as unknown as { asked: boolean }).asked = true; }, userChoice: Promise.resolve({ outcome: "accepted" }) });
      dispatchEvent(e);
    });
    await expect(guide.getByRole("button", { name: "홈 화면에 설치" })).toBeVisible({ timeout: 500 });
  }).toPass({ timeout: 15_000 });
  await guide.getByRole("button", { name: "홈 화면에 설치" }).click();
  expect(await page.evaluate(() => (window as unknown as { asked: boolean }).asked)).toBe(true);
  await expect(guide).toHaveCount(0); // 설치를 받아들이면 숨김

  if (info.project.name !== "mobile") return;
  // 아이폰 사파리: 공유 → 홈 화면에 추가 안내
  const { baseURL, viewport, deviceScaleFactor, isMobile, hasTouch, locale } = info.project.use;
  const ios = await browser.newContext({ baseURL, viewport, deviceScaleFactor, isMobile, hasTouch, locale, userAgent: IPHONE });
  const p = await ios.newPage();
  await p.goto("/");
  const g = p.getByRole("region", { name: "앱으로 설치" });
  await expect(g).toContainText("홈 화면에 추가");
  await expect(g.getByRole("img", { name: "공유" })).toBeVisible();
  await g.scrollIntoViewIfNeeded();
  await p.screenshot({ path: `${OUT}/mobile-02-install-ios.png` });
  // 이미 설치한 앱으로 열면(standalone) 안내가 없다
  await p.addInitScript(() => {
    const mm = window.matchMedia.bind(window);
    window.matchMedia = (q: string) => (q.includes("display-mode: standalone") ? { ...mm(q), matches: true, media: q } : mm(q));
  });
  await p.reload();
  await expect(p.getByRole("button", { name: "구글로 시작하기" }).first()).toBeVisible();
  await expect(p.getByRole("region", { name: "앱으로 설치" })).toHaveCount(0);
  await ios.close();
});
