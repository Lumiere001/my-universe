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
```

- 가짜 데이터 모드에서 글에 `[끊김]` 을 넣으면 연결 끊김 → "이어서 하기"를, "끝내고 싶" 같은 말을 넣으면 돌봄 화면을 볼 수 있다(진짜 위기 감지는 백엔드 몫).
- Vercel: Root Directory = `infra/frontend`, 프레임워크 Next.js 자동 인식. 환경변수는 `.env.example` 의 이름 그대로.
