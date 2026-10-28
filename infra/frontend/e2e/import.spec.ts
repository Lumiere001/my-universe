// 지난 일기 가져오기 · 글 파일 여러 개(2026-10-28, 가짜 데이터 모드): 가상 인물 하늘의 메모장 일기 3편(e2e/fixtures —
// UTF-8 BOM · UTF-8 · CP949)을 한꺼번에 골라 미리 보기(날 차례 · 건너뛰는 까닭 · 어림값) → 멈추기 · 이어 하기 → 셋을 묶은 ZIP 을 다시 고르면 '이미 있던 글'.
// 캡처는 docs/screens/ws17/<기기>-files-NN-이름.png
import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { decode, titleDay } from "../app/import/zip";

const OUT = path.resolve(__dirname, "../../../docs/screens/ws17");
const FIX = path.resolve(__dirname, "fixtures");
// 경로와 내용(buffer)을 섞어 고를 수 없어 모두 내용으로
const DIARIES = ["haneul-2026-09-27.txt", "haneul-2026-10-01.txt", "haneul-memo.txt"]
  .map((name) => ({ name, mimeType: "text/plain", buffer: readFileSync(path.join(FIX, name)) }));

test.describe("글 파일 읽기(화면 단위)", () => {
  test("메모장 글자 판: UTF-8(BOM 있든 없든) · CP949 · UTF-16", () => {
    const utf8 = new TextEncoder().encode("오늘 일기");
    expect(decode(utf8)).toBe("오늘 일기");
    expect(decode(new Uint8Array([0xef, 0xbb, 0xbf, ...utf8]))).toBe("오늘 일기");                 // BOM 은 뗌
    expect(decode(new Uint8Array([0xbf, 0xc0, 0xb4, 0xc3, 0x20, 0xc0, 0xcf, 0xb1, 0xe2]))).toBe("오늘 일기");   // CP949(ANSI)
    const u16 = [0xff, 0xfe, ...[..."오늘"].flatMap((c) => [c.charCodeAt(0) & 255, c.charCodeAt(0) >> 8])];
    expect(decode(new Uint8Array(u16))).toBe("오늘");
  });

  test("제목 속 날짜: 연도가 없으면 저장한 날 이전의 가장 가까운 해", () => {
    const saved = new Date(2026, 0, 15);   // 2026-01-15 에 저장
    expect(titleDay("2026-10-03 일기", saved)).toBe("2026-10-03");
    expect(titleDay("2025년 9월 29일 저녁 산책", saved)).toBe("2025-09-29");
    expect(titleDay("12/31 한 해 정리", saved)).toBe("2025-12-31");     // 1월에 쓴 12/31 → 지난해
    expect(titleDay("1월 2일 새해", saved)).toBe("2026-01-02");
    expect(titleDay("2/30 이상한 날", saved)).toBe("");                  // 없는 날
    expect(titleDay("도서관 가는 길", saved)).toBe("");
  });
});

test("글 파일 여러 개 가져오기", async ({ page }, info) => {
  const dev = info.project.name;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const shot = (name: string) => page.screenshot({ path: `${OUT}/${dev}-files-${name}.png` });
  const progress = page.getByRole("region", { name: "가져오기 진행" });
  const fitsOneScreen = async () => expect(await page.evaluate(() => document.documentElement.scrollHeight - innerHeight)).toBeLessThanOrEqual(1);

  await page.goto("/import");
  await expect(page.getByRole("heading", { level: 1, name: "지난 일기 가져오기" })).toBeVisible();
  const where = page.getByRole("group", { name: "가져올 곳" });
  await expect(where.getByRole("button", { name: "글 파일 여러 개" })).toHaveAttribute("aria-pressed", "true");
  await where.getByRole("button", { name: "인스타그램 ZIP" }).click();
  await expect(page.getByLabel("ZIP 파일(또는 posts_1.json)")).toBeVisible();
  await where.getByRole("button", { name: "글 파일 여러 개" }).click();
  await fitsOneScreen();
  await shot("01-pick");

  await test.step("여러 파일 → 날 차례 · 건너뛰는 까닭 · 어림값", async () => {
    await page.getByLabel("글 파일(.txt · .md) 여러 개 또는 ZIP").setInputFiles([
      ...DIARIES,
      { name: "haneul-long.txt", mimeType: "text/plain", buffer: Buffer.from("긴 회고\n" + "가".repeat(8001)) },
      { name: "photo.jpg", mimeType: "image/jpeg", buffer: Buffer.from([0xff, 0xd8, 0xff]) },
    ]);
    await expect(page.getByRole("heading", { name: "글 4편을 찾았어요" })).toBeVisible();
    const items = page.getByRole("list", { name: "글 목록(최근 것부터)" }).getByRole("listitem");
    await expect(items).toHaveCount(4);
    await expect(items.nth(0)).toContainText("(저장한 날) 긴 회고 · 너무 길어 건너뜀(8,000자까지)");   // 날짜 없는 파일은 저장한 날(오늘)
    await expect(items.nth(1)).toContainText("2026-10-01 10월 첫날");                                 // 파일 이름 속 날짜
    await expect(items.nth(2)).toContainText("2026-09-29 2026년 9월 29일 저녁 산책");                  // CP949 · 첫 줄 속 날짜
    await expect(items.nth(3)).toContainText("2026-09-27 도서관 가는 길");                            // UTF-8 BOM
    await expect(page.getByText("글 파일이 아닌 1개는 뺐어요.", { exact: false })).toBeVisible();
    await expect(page.getByText("3편 · 예상 시간 약 3분 · 예상 비용 약 $0.45")).toBeVisible();
    if (dev === "pc") await fitsOneScreen();
    await shot("02-preview");
  });

  await test.step("오래된 것부터 한 편씩 → 멈추기 → 이어 하기", async () => {
    await page.getByRole("button", { name: "가져오기 시작" }).click();
    await progress.getByRole("button", { name: "멈추기" }).click();
    await expect(progress.getByRole("heading", { name: "멈췄어요" })).toBeVisible({ timeout: 30_000 });
    await progress.getByRole("button", { name: /이어서 가져오기/ }).click();
    await expect(progress.getByRole("heading", { name: "다 가져왔어요" })).toBeVisible({ timeout: 30_000 });
    await expect(progress).toContainText("3 / 3편 · 새로 정리 3편");
    const got = progress.getByRole("list", { name: "가져온 글" }).getByRole("link");
    await expect(got).toHaveText(["2026-09-27 도서관 가는 길", "2026-09-29 2026년 9월 29일 저녁 산책", "2026-10-01 10월 첫날"]);
    await shot("03-done");
  });

  await test.step("같은 글을 묶은 ZIP 다시 → 다시 정리하지 않음", async () => {
    await progress.getByRole("button", { name: "다른 파일 고르기" }).click();
    await page.getByLabel("글 파일(.txt · .md) 여러 개 또는 ZIP").setInputFiles(path.join(FIX, "haneul-diaries.zip"));
    await expect(page.getByRole("heading", { name: "글 3편을 찾았어요" })).toBeVisible();
    await page.getByRole("button", { name: "가져오기 시작" }).click();
    await expect(progress.getByRole("heading", { name: "다 가져왔어요" })).toBeVisible({ timeout: 30_000 });
    await expect(progress).toContainText("3 / 3편 · 새로 정리 0편 · 이미 있던 글 3편");
  });

  expect(errors).toEqual([]);
});
