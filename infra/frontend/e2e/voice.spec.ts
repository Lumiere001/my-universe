// 말로 쓰기 · 읽어 주기(WS21), 가짜 데이터 모드: 마이크(가짜 장치) 녹음 → 대화 턴 · 4.5MB 넘는 3분 녹음 파일 → 브라우저가 2분 조각으로
// 나눠 받아쓰기 → 긴 이야기는 '지금까지 정리' → 정리하기 → 요약 확인 · 읽어 주기 켜면 별지기 답을 읽음 · 쓰기 화면은 칸에 채움.
// 녹음은 코드가 만든 소리(220Hz 소리 2.4초 · 쉼 0.6초)라 사람 목소리 없음. 받아쓴 글은 가상 인물 하늘의 지어낸 말.
// 캡처는 docs/images/v8/<기기>-voice-NN-이름.png.
import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const OUT = path.resolve(__dirname, "../../../docs/images/v8");
const MB4 = 4 * 1024 * 1024;

// 마이크: 헤드리스 크롬의 가짜 장치는 macOS 권한에 막혀 멈추므로 Web Audio 소리(220Hz)를 마이크 대신 준다(MediaRecorder 는 진짜).
test.beforeEach(({ page }) => page.addInitScript(() => {
  navigator.mediaDevices.getUserMedia = async () => {
    const ac = new AudioContext(), o = ac.createOscillator(), d = ac.createMediaStreamDestination();
    o.frequency.value = 220; o.connect(d); o.start();
    return d.stream;
  };
}));

function wavFile(seconds: number, rate = 44100): Buffer {
  const n = Math.floor(seconds * rate), b = Buffer.alloc(44 + n * 2);
  b.write("RIFF", 0); b.writeUInt32LE(36 + n * 2, 4); b.write("WAVE", 8); b.write("fmt ", 12);
  b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22); b.writeUInt32LE(rate, 24);
  b.writeUInt32LE(rate * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write("data", 36); b.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) {
    const t = i / rate;
    b.writeInt16LE(t % 3 < 2.4 ? Math.round(Math.sin(2 * Math.PI * 220 * t) * 8000) : 0, 44 + i * 2);
  }
  return b;
}
const file = (name: string, buffer: Buffer, mimeType = "audio/wav") => ({ name, mimeType, buffer });
type VoiceLog = { __voicePieces?: number[]; __spoken?: string[] };
const pieces = (page: Page) => page.evaluate(() => (window as unknown as VoiceLog).__voicePieces ?? []);
const spoken = (page: Page) => page.evaluate(() => (window as unknown as VoiceLog).__spoken ?? []);

test("말로 이야기하기 → 요약 확인 · 읽어 주기 · 쓰기 칸 채우기", async ({ page }, info) => {
  const dev = info.project.name;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const shot = (name: string, full = false) => page.screenshot({ path: `${OUT}/${dev}-voice-${name}.png`, fullPage: full,
    style: full ? ".top .nav { visibility: hidden; }" : undefined });
  const talk = page.getByRole("region", { name: "대화" });
  const mine = talk.locator(".bubble.me");

  await test.step("읽어 주기 켜기 → 마이크로 말하기(가짜 장치) → 대화 턴 · 별지기 답을 읽음", async () => {
    await page.goto("/talk");
    await expect(talk.locator(".voice").first()).toBeVisible();
    const toggle = page.getByRole("button", { name: /읽어 주기/ });
    await expect(toggle).toHaveAttribute("aria-pressed", "false");               // 기본 꺼짐
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "말로 하기" }).click();
    await expect(page.getByRole("button", { name: /말 마치기/ })).toBeVisible();
    await shot("01-recording");
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: /말 마치기/ }).click();
    await expect(mine).toHaveCount(1);
    await expect(mine.first()).toContainText("동네 공원을 천천히 걸었어요");
    const reply = await talk.locator(".voice .bubble").last().innerText();
    await expect.poll(() => spoken(page)).toContain(reply);
    expect(await pieces(page)).toHaveLength(1);
  });

  await test.step("4.5MB 넘는 3분 녹음 파일 → 2분 조각 둘로 나눠 받아쓰기 → 긴 이야기는 바로 '지금까지 정리'", async () => {
    const big = wavFile(180);
    expect(big.length).toBeGreaterThan(4.5 * 1024 * 1024);
    await page.getByTestId("voice-file").setInputFiles(file("하늘-음성메모.wav", big));
    await expect(mine).toHaveCount(2);
    const sizes = (await pieces(page)).slice(1);
    expect(sizes).toHaveLength(2);
    expect(sizes.every((s) => s < MB4)).toBe(true);                                // Vercel 본문 한도 아래
    const secs = sizes.map((s) => (s - 44) / 32000);
    expect(secs[0]).toBeGreaterThan(114);
    expect(secs[0]).toBeLessThanOrEqual(120);                                      // 2분 앞 5초 안 조용한 곳에서 자름
    expect(Math.round(secs[0] + secs[1])).toBe(180);                               // 소리는 빠짐없이
    await expect(mine.last()).toContainText("포트폴리오를 한 장이라도");
    await page.getByText("지금까지 정리").click();
    await expect(page.locator("details")).toContainText("동네 공원");
    await shot("02-long-story", true);
  });

  await test.step("짧은 녹음 · 못 푸는 큰 파일 · 못 푸는 작은 파일(그대로 보냄)", async () => {
    await page.getByTestId("voice-file").setInputFiles(file("짧음.wav", wavFile(0.2)));
    await expect(page.locator(".err[role=alert]")).toContainText("너무 짧아요");
    await page.getByTestId("voice-file").setInputFiles(file("메모.m4a", Buffer.alloc(5 * 1024 * 1024, 7), "audio/mp4"));
    await expect(page.locator(".err[role=alert]")).toContainText("열 수 없는 녹음");
    await page.getByTestId("voice-file").setInputFiles(file("메모2.m4a", Buffer.alloc(2048, 7), "audio/mp4"));
    await expect(mine).toHaveCount(3);                                             // 4MB 아래는 그대로 보내 서버가 형식을 봄
  });

  await test.step("대화 마치고 정리하기 → 요약 확인 → 저장(저장 뒤 한마디도 읽음)", async () => {
    await page.getByRole("button", { name: "대화 마치고 정리하기" }).click();
    const card = page.getByTestId("confirm-card");
    await expect(card).toBeVisible();
    await card.getByRole("button", { name: "확인하고 우주에 저장" }).click();
    await expect(page.getByTestId("saved-message")).toBeVisible();
    const said = await page.getByTestId("saved-message").locator(".bubble").innerText();
    await expect.poll(() => spoken(page)).toContain(said);
  });

  await test.step("쓰기 화면: 녹음 파일을 받아쓴 글이 칸에 채워짐", async () => {
    await page.goto("/");
    const box = page.getByLabel(/마음껏 적어 주세요/);
    await box.fill("오늘의 첫 줄.");
    await page.getByTestId("voice-file").setInputFiles(file("짧은메모.wav", wavFile(4)));
    await expect(box).toHaveValue(/^오늘의 첫 줄\.\n.+/);
    await page.getByRole("button", { name: "말로 하기" }).scrollIntoViewIfNeeded();
    await shot("03-write");
  });

  await test.step("좁은 휴대폰(360px)에서도 가로로 넘치지 않음", async () => {
    await page.goto("/talk");
    await page.setViewportSize({ width: 360, height: 780 });
    await expect(page.getByRole("button", { name: "말로 하기" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
  });
  expect(errors).toEqual([]);
});
