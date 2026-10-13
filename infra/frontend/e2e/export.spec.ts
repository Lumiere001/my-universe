// WS15 관측 보고서 · JSON 내려받기(가짜 데이터 모드): 결과 카드의 관측 상태 · 한계 → 이 기록 JSON → 지난 기록에서 전체 JSON.
// 캡처는 docs/screens/ws15/<기기>-NN-이름.png. 가상 인물 하늘의 지어낸 글.
import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";

const OUT = path.resolve(__dirname, "../../../docs/screens/ws15");

test("관측 보고서 · JSON 내려받기", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const result = page.getByTestId("result");
  const saved = async (name: string) => {
    const [d] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name }).click()]);
    expect(d.suggestedFilename()).toMatch(/^my-universe-.+\.json$/);
    return JSON.parse(readFileSync((await d.path())!, "utf8"));
  };

  await test.step("결과 카드: 관측 상태 · 한계 · 이 기록 JSON", async () => {
    await page.goto("/");
    await page.getByLabel(/마음껏 적어/).fill("민수 형이랑 진로 이야기를 했다. 작은 팀도 알아보고 싶다.");
    await page.getByRole("button", { name: "우주에 띄우기" }).click();
    const obs = result.getByRole("region", { name: "관측 보고서" });
    await expect(obs).toBeVisible({ timeout: 15_000 });
    await expect(obs).toContainText("관측 상태");
    await expect(obs).toContainText("바뀜");
    await expect(obs.getByRole("listitem")).toHaveCount(3);
    await obs.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${OUT}/${info.project.name}-01-observation.png` });
    const j = await saved("이 기록 JSON 내려받기");
    expect(j.schema).toBe("my-universe-export/1");
    expect(j.scope).toBe("entry");
    expect(j.records).toHaveLength(1);
    expect(j.records[0].observation.state).toBe("바뀜");
  });

  await test.step("지난 기록: 전체 JSON", async () => {
    await page.getByRole("navigation", { name: "화면" }).getByRole("link", { name: "지난 기록", exact: true }).click();
    await expect(page.getByRole("button", { name: "전체 기록 JSON 내려받기" })).toBeVisible();
    await page.screenshot({ path: `${OUT}/${info.project.name}-02-history-export.png` });
    const j = await saved("전체 기록 JSON 내려받기");
    expect(j.scope).toBe("all");
  });

  expect(errors).toEqual([]);
});
