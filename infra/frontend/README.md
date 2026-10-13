# 나의 우주 화면 (Next.js, v8)

API 모양은 `docs/api-v8.md`. 온톨로지는 `app/core/ontology/v8.json` 을 `npm run sync:ontology` 로 `lib/ontology.json` 에 복사해 쓴다(손으로 고치지 않음).

```bash
cd infra/frontend
npm install
cp .env.example .env.local          # 값 채우기(로컬 전용, gitignore)
NEXT_PUBLIC_MOCK=1 npm run dev      # 백엔드 없이 가짜 데이터(가상 인물 하늘)로 보기 → http://localhost:3000
npm run dev                         # 백엔드(NEXT_PUBLIC_API_BASE, 기본 http://localhost:8001)와 함께
npm run build                       # 타입 검사 포함
npx playwright install chromium && npm run e2e   # 휴대폰 · PC 핵심 흐름 + 캡처(docs/images/v8/)
npx playwright test -c playwright.real.config.ts  # 실제 백엔드(:8001)에 붙여 같은 흐름(유료 일기 기기당 1편) → docs/e2e-real.md
npx playwright test -c playwright.landing.config.ts  # 소개 · 설치형 웹앱(로그아웃 실제 모드, 외부 호출 0) → docs/screens/ws26/
node scripts/make-images.mjs                         # 아이콘 · 공유 미리보기 · 소개 캡처 다시 만들기(public/)
```

- 가짜 데이터 모드에서 글에 `[끊김]` 을 넣으면 연결 끊김 → "이어서 하기"를, "끝내고 싶" 같은 말을 넣으면 위기 글 결과(평소 카드 + 위로 한마디 + 안부 한 줄, 시험 단계)를 볼 수 있다(진짜 위기 감지는 백엔드 몫).
- Vercel: Root Directory = `infra/frontend`, 프레임워크 Next.js 자동 인식. 환경변수는 `.env.example` 의 이름 그대로.
- 소개 · 설치형 웹앱(WS26): 로그아웃 상태면 `components/Landing.tsx`(소개 + '구글로 시작하기'), 로그인하면 바로 앱 화면(`components/Shell.tsx` 가 가름).
  `public/manifest.webmanifest` · `public/icons/` · `public/sw.js`(오프라인 안내 화면 `public/offline.html` 하나만 캐시 — 일기 · API 응답은 캐시하지 않음) · `components/InstallGuide.tsx`(안드로이드 '앱 설치' 버튼, 아이폰 공유 → 홈 화면에 추가 안내, 설치했으면 숨김 — 소개 · 설정 화면).
  공유 미리보기(OG · 트위터 카드) · manifest 연결은 `lib/site.ts`, 검색은 `app/robots.ts` · `app/sitemap.ts`(소개 · /privacy 만) · `next.config.ts`(로그인 뒤 화면 `X-Robots-Tag: noindex`). 사이트 주소는 `NEXT_PUBLIC_SITE_URL`(비우면 운영 주소).
