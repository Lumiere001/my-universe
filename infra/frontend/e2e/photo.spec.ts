// WS18 사진(손글씨) 입력(가짜 데이터 모드): 형식 밖 파일 · 큰 HEIC 는 친절한 오류 → 두 쪽 순서 바꾸기 · 빼기 →
// 글자 읽기(쪽 순서대로 쓰기 칸에 채움, 사진은 화면에서도 비움) → 고쳐서 띄우기. 사진은 tests/fixtures/photos 의 가상 손글씨(지호).
// 실제 글자 읽기(Upstage) · 로컬 백엔드 확인은 e2e-real/ws18.spec.ts.
import { expect, test } from "@playwright/test";
import path from "node:path";

const PHOTOS = path.resolve(__dirname, "../../../tests/fixtures/photos");

test("사진으로 쓰기", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/write");
  const box = page.getByRole("group", { name: "사진으로 쓰기" });
  const input = box.getByLabel(/사진에서 글자 읽기/);
  const list = box.getByRole("list", { name: "읽을 사진(쪽 순서)" });
  const diary = page.getByLabel(/마음껏 적어/);

  await test.step("형식 밖 파일은 빼고 친절한 오류, 큰 HEIC(크롬이 못 줄임)도 오류", async () => {
    await input.setInputFiles([{ name: "스캔.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7") }]);
    await expect(box.getByRole("alert")).toContainText("jpg · png · heic 사진만");
    await expect(list).toHaveCount(0);
    await input.setInputFiles([{ name: "큰사진.heic", mimeType: "image/heic", buffer: Buffer.alloc(4_100_000, 1) }]);
    await box.getByRole("button", { name: "사진 1장 글자 읽기" }).click();
    await expect(box.getByRole("alert")).toContainText("높은 호환성");
    await list.getByRole("button", { name: "1쪽 빼기" }).click();
    await expect(list).toHaveCount(0);
  });

  await test.step("두 쪽을 거꾸로 올리고 순서 바꾸기 → 읽으면 쓰기 칸에 쪽 순서대로", async () => {
    await input.setInputFiles([path.join(PHOTOS, "jiho-1012-p2.jpg"), path.join(PHOTOS, "jiho-1012-p1.jpg")]);
    await expect(list.getByRole("listitem")).toHaveCount(2);
    await list.getByRole("button", { name: "1쪽 뒤로" }).click();
    await expect(list.getByRole("listitem").first()).toContainText("jiho-1012-p1.jpg");
    await expect(list.getByRole("listitem").last()).toContainText("jiho-1012-p2.jpg");
    await input.setInputFiles([path.join(PHOTOS, "jiho-1010.heic")]);   // 크롬은 HEIC 를 못 그려 4MB 아래면 그대로 보냄
    await expect(list.getByRole("listitem")).toHaveCount(3);
    await list.getByRole("button", { name: "3쪽 빼기" }).click();
    await box.getByRole("button", { name: "사진 2장 글자 읽기" }).click();
    await expect(box.getByRole("status")).toContainText("2쪽을 읽어 글 칸에 채웠어요");
    await expect(list).toHaveCount(0);                                 // 읽은 사진은 화면에서도 비움
    const text = await diary.inputValue();
    expect(text.indexOf("1번째 사진")).toBeGreaterThanOrEqual(0);
    expect(text.indexOf("2번째 사진")).toBeGreaterThan(text.indexOf("1번째 사진"));
  });

  await test.step("HEIC 한 장(줄이지 않고 그대로) → 읽은 글은 이어 붙음 → 고쳐서 띄우기", async () => {
    await input.setInputFiles([path.join(PHOTOS, "jiho-1010.heic")]);
    await box.getByRole("button", { name: "사진 1장 글자 읽기" }).click();
    await expect(diary).toHaveValue(/3번째 사진/);
    await diary.fill((await diary.inputValue()).replace("도서관", "학교 도서관"));
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    await expect(page.getByTestId("result")).toBeVisible({ timeout: 15_000 });
  });
  expect(errors).toEqual([]);
});
