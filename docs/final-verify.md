# 10/17 판 최종 확인

실행 2026-10-08 · 브랜치 `final-verify`(master `c746bee` 위) · 시험은 가상 인물 데이터만, 원문은 넣지 않는다.

## 결과

| # | 확인 | 결과 | 숫자 · 근거 |
| --- | --- | --- | --- |
| 1 | `uv sync && uv run --frozen pytest -q` | 통과 | 463 → 고친 뒤 464 통과(vs-34 시험 1개 추가) |
| 2a | 골든셋 `eval/run.py`(외부 호출 없음) | 예상대로 | 관문 칸은 "불합격"으로 찍힘 — live 사례 14개(팩폭 6 · 말 걸기 8)가 미실행이라서. 실행된 관문 사례는 모두 통과, 회귀 0, 호출 0 |
| 2b | 골든셋 `--live --crisis-llm` 1회 | **관문 통과** | Solar 45번 · $0.0276. 위기 규칙만 16/16 · 오탐 0/14, 규칙 + LLM 16/16 · 오탐 0/14. 팩폭 28/28, 말 걸기 23/23(vs-34 통과). 기준선 대비 떨어진 사례 cn-12 하나 — 애매 사례(LLM 이 위기 쪽으로 봄, 합격 판정에 안 씀). `eval/results/2026-10-08-all-live-crisis_llm.json`, `docs/eval-v8.md` 결과 칸 |
| 3a | 화면 `npm ci` → `npm run build`(타입 검사) | 통과 | 취약점 0, 7개 화면 정적 빌드 |
| 3b | 가짜 모드 e2e `npm run e2e` | 통과 | 휴대폰 · PC 2/2(고친 뒤 다시 2/2) |
| 4 | 실제 모드 e2e(`playwright.real.config.ts`, 백엔드 :8001) | 통과 | 휴대폰 · PC 2/2. 유료 일기는 휴대폰 1편만(`REAL_DIARY=mobile`) |
| 4-1 | 로그인 | 통과 | 시험용 계정 → 위 막대 |
| 4-2 | 일기 → SSE 진행 → 결과 카드 | 통과 | 진행 단계 바뀜, 처리 중 새로고침 → 이어서 하기, 결과까지 17초. 생각 4 · 관계 3 · 지난 생각 10 · 닿은 순간 1 |
| 4-3 | 점선 맞아요/아니에요 | 통과 | 관계 3개 모두 `needs_confirm=true`, 화면 "이 연결이 맞나요" 3개(개수 일치 검사), '맞아요' 저장 |
| 4-4 | 피드백 저장 | 통과 | 좋아요 · 맞아요 · 지켰어요 · 불편한 점 → feedback 표 4줄, 다시 불러오면 "다짐 지켜짐" |
| 4-5 | 위기 글 돌봄 | 통과(고친 뒤) | 외부 호출 0(runs 표), 돌봄 문장 줄 겹침 없음 · 119/112 안내 한 번 |
| 4-6 | 우주 · 사람 고르기 | 통과(데이터 다시 넣은 뒤) | 해 4 · 작은 별 6 · 행성 25 · 선 35 · 쌍행성 5 · 북극성. 민수 · 지은 각각 행성 1개가 빛남 |
| 4-7 | 설정 계정 지우기 단추 | 통과 | 보이고, '지우기' 입력 전엔 꺼져 있음. 누르지 않음 |
| 4-8 | 로그아웃 | 통과 | 새로고침 뒤에도 로그인 문 |
| 4-9 | 비용 | $0.1020 | 일기 1편: 외부 호출 5번(Studio 2번 · Solar 3번). 위기 글 2편 호출 0 |
| 5-1 | 시험용 계정 토큰으로 로컬 Data API | 막힘 | `/rest/v1/{runs, entries, thoughts, people, feedback, profiles}` 모두 403 · 42501(permission denied) |
| 5-2 | `/docs` · `/openapi.json` · `/redoc`(API_DOCS 없음) | 404 | 셋 다 404 |
| 5-3 | `ALLOWED_EMAILS=다른 이메일`로 띄운 백엔드(:8002) | 403 not_allowed | tester@ 토큰으로 `/universe` → 403 `not_allowed`. 같은 토큰이 :8001(목록 없음)에선 200, 토큰 없으면 401 |
| 6 | vs-34(안전한 기본 문장 반복) | 고침 | 아래 |

비용 원장(`runs/cost_ledger.jsonl`) 합계 $3.8917 → $4.0213(`final-verify` 줄 2개).

## 고친 것

| 문제 | 고침 |
| --- | --- |
| vs-34: 두 번 실패하면 쓰는 안전한 기본 문장이 지난 한마디와 같아 반복 검사에 걸림 | `app/service/voice/__init__.py` `SAFE` 를 말투 · 위로 여부마다 2개로, `checks.repeat_problems` 로 지난 한마디와 겹치지 않는 첫 문장을 고름. 시험 `test_safe_line_skips_past_repeat` |
| 돌봄 화면에 "지금 당장 위험하다면 119나 112에…"(서버 문장)와 "지금 위험하다면 112 · 119로도…"(화면 고정 문장)가 겹침. 여러 줄 돌봄 문장이 한 덩어리로 붙음 | `components/ResultCard.tsx`: 돌봄 문장에 119/112 가 있으면 고정 문장을 안 보임, 줄바꿈 살림(`pre-line`) |
| 민수 · 지은이 어느 행성과도 안 이어짐(e2e-real 남은 문제 2) | 코드는 eb31bbf 에서 이미 고쳐졌고 로컬 데모 데이터가 그 전에 넣은 것이었음. `uv run --frozen python -m app.core.seed demo` 로 다시 넣음(외부 호출 없음) → 각 1개. 시험 끝난 뒤에도 한 번 더 넣어 되고 싶은 모습 · 기록을 원래대로 |
| 실제 모드 e2e 가 기기마다 유료 일기를 씀, 캡처를 다 남김 | `e2e-real/real.spec.ts`: `REAL_DIARY`(그 기기만 유료 일기) · `REAL_SHOTS`(남길 캡처) · `REAL_OUT`, 점선 버튼 개수 · 사람 빛남 · 돌봄 겹침 · 계정 지우기 단추 검사 추가 |

e2e-real 남은 문제 3(점선이 실제로 안 나옴)은 이번 실행에서 점선 3개가 나와 눌러 봄.

## 남은 것

- 하루 글 수 상한이 기록 `created_at` 으로 세져, 데모를 다시 넣은 날 tester@ 는 새 글을 못 씀 → 이번에도 `DAILY_ENTRY_LIMIT=60` 으로 띄움(시험용 계정만의 문제).
- 가치 이름 · 빈 주제가 작은 별 이름이 되는 문제는 결정 필요(고치지 않음).

## 다시 돌리기

```bash
DAILY_ENTRY_LIMIT=60 uv run --frozen uvicorn main:app --port 8001
cd infra/frontend && REAL_OUT=docs/images/v8-final REAL_DIARY=mobile \
  REAL_SHOTS=mobile-04-person,mobile-10-result,mobile-13-care,mobile-19-settings-kept,pc-02-universe,pc-06-history-entry \
  npx playwright test -c playwright.real.config.ts
cd ../.. && uv run --frozen python -m app.core.seed demo   # 되고 싶은 모습 등 데모로 되돌림
```

## 캡처 (`docs/images/v8-final/`)

| 파일 | 내용 |
| --- | --- |
| `mobile-04-person.png` | 휴대폰 우주, 민수 고름(그 행성만 밝고 나머지 흐림) |
| `mobile-10-result.png` | 휴대폰 결과 카드(전체, 점선 3개의 맞아요/아니에요) |
| `mobile-13-care.png` | 휴대폰 돌봄 화면 |
| `mobile-19-settings-kept.png` | 휴대폰 설정(전체, 맨 아래 계정 지우기) |
| `pc-02-universe.png` | PC 우주 |
| `pc-06-history-entry.png` | PC 결과 카드(지난 기록 하나 — PC 는 유료 일기를 안 써서 데모 기록) |
