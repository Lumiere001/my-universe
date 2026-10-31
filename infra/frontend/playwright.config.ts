// 화면 기록 겸 e2e: 가짜 데이터 모드로 빌드해 띄우고, 휴대폰(390x844)으로 핵심 흐름을 돌며 캡처한다(PRD v9: 휴대폰 사용자만, PC 화면은 이번에 안 함).
import { defineConfig } from "@playwright/test";

const PORT = Number(process.env.E2E_PORT) || 3100; // 다른 갈래와 겹치면 E2E_PORT 로 바꿈
export default defineConfig({
  testDir: "e2e",
  timeout: 180_000,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    reducedMotion: "reduce", // 우주가 저절로 돌지 않게(캡처 · 클릭 좌표 고정)
    locale: "ko-KR",
    // 헤드리스에서 WebGL(three.js)을 그리려면 소프트웨어 GL 이 필요하다
    launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] },
  },
  projects: [
    { name: "mobile", use: { browserName: "chromium", viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: `npx next build && npx next start -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    env: { NEXT_PUBLIC_MOCK: "1" },
    timeout: 300_000,
    reuseExistingServer: !!process.env.E2E_REUSE,   // 고치는 동안 떠 있는 가짜 데이터 서버(web-mock)에 붙이기: E2E_REUSE=1 E2E_PORT=3020
  },
});
