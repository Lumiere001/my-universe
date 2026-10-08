// 실제 모드 e2e: 로컬 백엔드(:8001) · 로컬 Supabase · Chroma 에 붙여 핵심 흐름을 끝까지 돈다(유료 호출 있음, 기기마다 일기 1편 + 위기 글 1편).
// 먼저 백엔드를 띄운다: uv run --frozen uvicorn main:app --port 8001. 캡처는 docs/images/v8-real/.
// 백엔드 CORS 기본값(FRONTEND_ORIGIN)이 http://localhost:3000 이라 3000 에 띄운다.
import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  testDir: "e2e-real",
  timeout: 600_000,
  use: { ...base.use, baseURL: "http://localhost:3000" },
  webServer: {
    command: "npx next build && npx next start -p 3000",
    url: "http://localhost:3000",
    env: { NEXT_PUBLIC_MOCK: "0" },
    timeout: 300_000,
    reuseExistingServer: false,
  },
});
