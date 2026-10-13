// 소개 · 설치형 웹앱 e2e: 로그인 안 한 실제 모드로 빌드해 휴대폰(390) · PC(1440)로 돈다.
// Supabase · API 주소는 닿지 않는 가짜라 외부 호출이 없고 시험 계정도 필요 없다(로그인 상태는 가짜 세션 · 가짜 API 로 흉내).
// 실행: npx playwright test -c playwright.landing.config.ts. 캡처는 docs/screens/ws26/<기기>-NN-이름.png
import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

const PORT = 3101;
export const FAKE = { supabase: "http://127.0.0.1:54399", api: "http://127.0.0.1:54398" };

export default defineConfig({
  ...base,
  testDir: "e2e-landing",
  timeout: 120_000,
  use: { ...base.use, baseURL: `http://localhost:${PORT}` },
  webServer: {
    command: `npx next build && npx next start -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    env: { NEXT_PUBLIC_MOCK: "0", NEXT_PUBLIC_DEV_LOGIN: "0", NEXT_PUBLIC_SUPABASE_URL: FAKE.supabase,
      NEXT_PUBLIC_SUPABASE_ANON_KEY: "e2e-landing", NEXT_PUBLIC_API_BASE: FAKE.api },
    timeout: 300_000,
    reuseExistingServer: false,
  },
});
