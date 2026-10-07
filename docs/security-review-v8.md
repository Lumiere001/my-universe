# 나의 우주 v8 보안 · 개인정보 검토 (2026-10-08)

범위: master `7265fc9` 의 FastAPI 백엔드(main.py, app/), supabase/migrations, Next.js 화면(infra/frontend), Docker · Vercel 설정.
방법: 코드를 읽고, 로컬 스택(Supabase 54321/54322 · Chroma 8000 · 백엔드 8011)에 시험용 계정 두 개(tester@ · 검토용으로 만든 뒤 지운 sec-review@)로 직접 요청했다.
유료 호출(Studio · Solar)은 하지 않았다. 시험 데이터는 가상 인물(하늘)뿐. `uv run --frozen pytest -q` → 386 passed.

표시: **재현함** = 로컬에서 직접 확인함, **코드** = 코드로 확인함(실행은 안 함), **확인 필요** = 추측이거나 바깥 서비스 설정에 달림.

## 요약

| 심각도 | 개수 | 핵심 |
| --- | --- | --- |
| 높음 | 1 | Supabase Data API(PostgREST)로 사용자가 자기 `runs` 행을 고치거나 지워 비용 상한을 없앨 수 있다 |
| 중간 | 10 | 이름 가리기에서 빠지는 이름, Studio 업로드 파일 남음, 계정 삭제 없음, 로그아웃 없음, 평문 위기 표시, 아무나 가입 가능, 실제 일기가 git 에 있음, resume 비용, 인스턴스 여러 개 |
| 낮음 | 12 | 토큰 캐시 60초, FK 로 존재 여부 드러남, /docs 공개, NUL 입력 500, 로컬 포트, 문서 이름 불일치 등 |

잘 된 것(재현함): 모든 사용자 엔드포인트가 `get_user` 를 거친다(/health · /ontology 만 공개). 다른 사용자의 entry · person · question · relation · thought(다짐) id 로 읽기 · 고치기 · 지우기 · 이어 하기 · 피드백을 보내면 모두 404/409 로 막히고, A 의 /universe · /people · /aspiration 은 그대로였다(34개 확인 중 예상 밖 0개). 모든 표 15개에 RLS(`using` + `with check`)가 있고 anon 은 거부된다. 백엔드는 요청마다 `set local role authenticated` + JWT claim 을 걸어 코드가 user_id 를 빠뜨려도 RLS 가 막는다. 422 응답이 원문을 되돌려 보내지 않는다. Chroma 메타에는 user_id · entry_id · star_id · written_at · kind 만 있고 문서는 비어 있다(tester 61개 확인). git 에 추적되는 파일 · 이력에 키 모양 문자열 없음, .env* 는 추적되지 않음.

## 높음

### H1. PostgREST 로 비용 상한 · 서버 규칙 우회 — 재현함
- 위치: `supabase/migrations/20261008000000_v8_init.sql:177-179`(authenticated 에 모든 표 CRUD), `app/repository/diary.py:320-322`(month_cost = runs 합계)
- 문제: 화면이 공개하는 anon 키 + 사용자 자신의 access token 이면 Supabase REST(`/rest/v1/*`)로 자기 행을 마음대로 쓸 수 있다. RLS 는 "자기 행"만 보장하지 서버 규칙(비용 상한, 상태 값, 팩폭 경고 확인)은 지키지 않는다.
- 재현: B 토큰으로 `POST /rest/v1/runs {"user_id": B, "step": "x", "est_usd": -100}` → 201, 그 뒤 `GET /stats` 의 `month_cost_usd` = **-100.0**. `DELETE /rest/v1/runs?user_id=eq.B` → 200. `PATCH /rest/v1/profiles {"settings": {"tone": "팩폭", "fact_bomb_ack": false}}` → 200, `/me` tone = 팩폭(API 는 409 로 막는 조합). 일일 한도도 `entries` 행 수라(아래 L5) 같은 길로 지울 수 있다. → 한 사용자가 Studio · Solar 비용을 끝없이 키울 수 있다.
- 고치기(하나 고름): (a) 표를 노출되지 않는 스키마(예: `app`)로 옮기거나 Supabase 설정에서 `public` 을 Data API 에서 뺀다. (b) 백엔드 전용 역할(예: `app_user`, PostgREST 가 모르는 역할)을 만들어 `set local role app_user` 로 바꾸고 RLS 정책을 그 역할에 걸고 `authenticated` 의 권한은 revoke. 함께 `runs.est_usd >= 0` check 를 단다.

## 중간

### M1. 이름 가리기가 놓치는 이름은 그대로 외부로 나간다 — 재현함(순수 함수)
- 위치: `app/service/safety/pseudonym.py:34`(CAND), `:38`(LOOSE), `:182-187`(assert_no_real_names 는 등록된 이름만 검사)
- 문제: 새 이름은 호칭(선배 · 씨 …)이나 정해진 조사가 붙어야 잡힌다. 등록 안 된 이름은 guard 도 모른다.
- 재현: `mask("오늘 철수 만났다.", [])` → 그대로, `"김영희 생일 축하했다."` → 그대로, `"Kevin이랑 밥 먹었다."` → 그대로, `"수빈과 카페에서 얘기했다."` → 그대로(`과` 가 LOOSE 에 없음). 이 글은 Studio · Solar 로 실명째 나간다.
- 고치기: LOOSE 에 `과|이랑|하고|의` 등 더하기, 조사 없는 2~3글자 + 사람 행동 낱말 문장도 후보로, 영문 이름(대문자 시작 낱말) 후보 추가. 화면에서 "보내기 전 이 이름들을 가립니다" 확인을 보여 주면 가장 확실하다. 개인정보 안내문에 "등록 안 된 이름은 가려지지 않을 수 있음"을 적는다.

### M2. Studio 에 올린 파일(가명 일기 HTML)을 지우지 않는다 — 코드, 보관 기간은 확인 필요
- 위치: `app/agents/studio.py:34`(`files.create`), 저장소 어디에도 `files.delete` 없음
- 문제: 일기 한 편마다 기록 · 관측 입력 파일이 Upstage Files 에 남는다(가명이지만 M1 때문에 실명이 섞일 수 있음). 응답 객체 보관 여부도 확인 필요.
- 고치기: `_once` 에서 `try/finally: client().files.delete(up.id)`(실패는 기록만). Upstage 의 Files · Responses 보관 정책을 확인해 개인정보 안내에 적는다.

### M3. 계정 삭제 경로가 없고, 지워도 벡터가 남는다 — 코드
- 위치: API 전체(없음), 약속은 `docs/tech-explainer-v8.md:48`("계정을 지우면 다 지운다"), 벡터는 `app/repository/vectors.py`(DB FK 와 무관)
- 문제: auth.users 를 지우면 DB 행은 cascade 로 지워지지만 Chroma 벡터 · Studio 파일은 남는다. 사용자가 스스로 지울 방법도 없다.
- 고치기: `DELETE /me` — `seed.wipe` 와 같은 순서로 DB · `repo.vectors.delete(uid)` 를 지운 뒤 서비스 키로 `auth/v1/admin/users/{uid}` 삭제(서비스 키는 이 경로에서만, 서버 환경변수로). 화면 설정에 버튼 + 확인.

### M4. 화면에 로그아웃이 없다 — 코드
- 위치: `infra/frontend/components/Shell.tsx`(signOut 호출 없음, `app/settings` 에도 없음)
- 문제: 공용 · 동아리방 PC 에서 로그인하면 다음 사람이 일기를 그대로 본다. 토큰은 supabase-js 기본값대로 localStorage 에 남는다(refresh token 포함).
- 고치기: 위 막대나 설정에 `sb.auth.signOut()` 버튼 하나.

### M5. 평문 칸에 위기 · 마음 상태 표시가 남는다 — 코드
- 위치: `supabase/migrations/...sql:18`(`entries.crisis`), `:140`(`messages.mode = 'care' · 'comfort'`), `:151`(`feedback.value` 예: "오늘은 위로만"), `:165`(`runs.meta.situations` 예: "무거운 날"), `:66`(`people.relation`)
- 문제: DB 를 볼 수 있는 사람(운영자 · Supabase 대시보드 · 백업)이 "누가 언제 위기 글을 썼는지"를 원문 없이도 안다. 아래 평문 표 참고.
- 고치기: `crisis` · `mode` 는 enc 로 옮기고 목록 · 우주는 풀어서 거른다(행 수가 작아 충분). runs.meta 의 situations 는 빼거나 "무거운 날"류는 남기지 않는다. relation 은 forget() 에 쓰이므로 enc 의 people 안으로 옮겨도 된다.

### M6. 아무 구글 계정(설정에 따라 이메일 가입)으로 들어와 비용을 쓸 수 있다 — 코드, 클라우드 설정은 확인 필요
- 위치: `app/core/auth.py:23-45`(토큰만 확인, 허용 목록 없음), `supabase/config.toml:165,200`(로컬은 가입 허용)
- 문제: 팀원 전용인데 주소를 아는 누구나 가입 → 사람마다 월 $5 · 하루 10편이라 전체 비용 상한이 없다.
- 고치기: `ALLOWED_EMAILS`(쉼표 목록) 환경변수를 두고 `verify` 에서 이메일이 목록에 없으면 403. 클라우드 Supabase 는 Email 가입을 끈다.

### M7. 동규의 실제 일기 파일이 git 에 들어 있다 — 코드(파일은 열지 않음)
- 위치: `data/samples/2026-09-25-독서노트.md`, `data/samples/2026-10-01-일기.txt`(git ls-files · origin/master 에 있음, 저장소는 PRIVATE)
- 문제: 저장소를 팀원 · 채점자에게 공유하거나 공개로 바꾸면 그대로 노출된다. 이력에도 남는다. (배포 번들 · Docker 이미지에서는 `.vercelignore` · `.dockerignore` 가 `data` 를 뺀다.)
- 고치기: `git rm --cached` + `.gitignore` 에 추가, 이미 push 된 이력은 동규 판단으로 filter-repo(강제 push 필요 → 결정 필요).

### M8. resume 은 비용 상한을 보지 않는다 — 코드
- 위치: `app/api/diary.py:115-120`(상한 검사는 `_create` `:84-87` 에만)
- 문제: Studio 가 같은 입력에 계속 실패(studio_bad_output 등)하면 '이어서 하기'를 누를 때마다 Studio 2회(+$0.10) 가 나가고, 월 상한을 넘어도 막히지 않는다.
- 고치기: resume 에도 `month_cost >= cap` 검사, 기록마다 resume 횟수 상한(예: 3회, steps 에 세기).

### M9. 실행 중 표시(`_running`)가 프로세스 메모리에만 있다 — 코드, Vercel 동작은 확인 필요
- 위치: `app/api/diary.py:26,39-42,136-137`
- 문제: Vercel 처럼 인스턴스가 여러 개면 다른 인스턴스는 그 기록을 "멈춤(failed)"으로 보여 주고 resume 을 허락한다 → 같은 기록이 두 번 돌아 비용 두 배, 저장 단계에서 같은 생각 id 로 충돌. 또 Vercel 은 손님이 끊으면 함수가 멈출 수 있어 기록이 processing 으로 남는다.
- 고치기: `entries.updated_at` 이 최근(예: 5분 안)이면 processing 을 그대로 두고 resume 을 409. 또는 DB 에서 `update entries set status='processing' where id=… and status<>'processing'` 로 잠금.

### M10. 로컬 Chroma(8000) · Supabase(54321/54322)가 모든 인터페이스에서 인증 없이 열려 있다 — 재현함(로컬)
- 위치: `docker-compose.yml:12`, 로컬 supabase 스택(`lsof` 로 `*:8000`, `*:54322` 확인)
- 문제: 같은 와이파이(학교 · 카페)에서 누구나 Chroma 의 모든 사용자 벡터 · 메타를 읽고 지울 수 있고, 로컬 DB 는 공개된 기본 비밀번호다. 지금은 가상 데이터라 영향이 작지만 실제 일기를 로컬에 넣으면 그대로 노출.
- 고치기: compose 포트를 `127.0.0.1:${CHROMA_HOST_PORT:-8000}:8000` 처럼 묶는다(백엔드 · 화면도 같음). 실제 일기는 로컬 스택에 넣지 않는다.

## 낮음

| # | 위치 | 문제 | 근거 | 고치기 |
| --- | --- | --- | --- | --- |
| L1 | `app/core/auth.py:16,24-28` | 로그아웃(전역)한 토큰이 최대 60초 더 통한다 | 재현함: 로그아웃 직후 `/me` 200, 62초 뒤 401 | 그대로 둬도 됨(문서화). 줄이려면 TTL 15초 |
| L2 | `app/core/auth.py:36-37` | Supabase 가 5xx · JSON 아닌 답을 주면 401(재로그인) 또는 500 | 코드 | `r.status_code >= 500` → 503, `r.json()` 실패 → 503 |
| L3 | 마이그레이션 FK 전체 | FK 검사는 RLS 를 거치지 않아 남의 id 존재 여부가 드러나고, 남의 기록에 자기 행을 매달 수 있다 | 재현함: B 가 A 의 entry_id 로 messages 삽입 201, 없는 id 는 409. A 의 기록 id 로 B 가 entries 삽입 → 23505 | id 가 48비트 무작위라 추측은 어려움. H1 을 고치면 같이 닫힘(PostgREST 를 막으면 B 가 임의 id 를 넣을 길이 없음) |
| L4 | `app/api/diary.py:143` | 남의 기록이라도 실행 중이면 404 대신 409 | 코드 | 소유 확인 뒤 `_running` 검사 |
| L5 | `app/repository/diary.py:325-327` | 하루 글 수 = 지금 남은 행 수라, 쓰고 지우면 하루 10편을 넘는다(월 상한은 남음) | 코드 | runs 의 `step='safety'` 행 수로 센다 |
| L6 | `main.py:17` | `/docs` · `/openapi.json` 공개 | 재현함 200 | 배포에서 `docs_url=None, openapi_url=None`(환경변수로) |
| L7 | `app/models/__init__.py:63,69` 외 | 평문 칸(relation 등)에 NUL 문자 → 500, uvicorn 이 traceback 을 찍음(값은 안 찍힘) | 재현함: `relation="친구\u0000…"` → 500, 로그에 DataError 만 | `In` 에 NUL 제거 validator 하나 |
| L8 | `app/repository/diary.py:119-135` | 사람 지우기가 `entries.steps_enc`(끊긴 기록의 단계 저장값) · 피드백 글 · Chroma 는 고치지 않는다 | 코드 | ENC 목록에 steps_enc · feedback 추가 |
| L9 | `app/repository/diary.py:210-226` | 기록 지우기 뒤에 그 기록에서 생긴 작은 별 · 자동 등록 사람 · 피드백(target_id)이 남는다 | 코드 | 쓰는 생각이 없는 별 · auto 사람 정리 |
| L10 | `infra/frontend`(next.config 없음) | CSP · frame-ancestors 같은 보안 헤더 없음, 토큰은 localStorage | 코드. dangerouslySetInnerHTML · 외부 링크 · eval 없음(XSS 길은 지금 안 보임) | `next.config` headers 에 CSP(`connect-src` = API · Supabase), `X-Frame-Options: DENY` |
| L11 | `deploy/MORNING.md:103` | 비용 한도 이름이 코드와 다르다(`MAX_ENTRIES_PER_DAY` · `MONTHLY_BUDGET_USD` ↔ `DAILY_ENTRY_LIMIT` · `MONTHLY_COST_CAP_USD`) | 코드. 기본값(10편 · $5)은 적용됨 | 문서 이름 고치기 |
| L12 | `app/core/security.py` | 마스터 키 하나 · 교체 경로 없음(키를 잃으면 전부, 새 나면 전부) | 코드 | 정보. 키를 Vercel 에만 두고 사본은 비밀번호 관리자에. 나중에 키 버전 바이트 |

## 평문으로 남는 칸 (DB · Chroma · 로그)

| 곳 | 평문 칸 | 무엇이 드러나나 | 암호화된 것(enc) |
| --- | --- | --- | --- |
| entries | written_at, weather, status, step, **crisis**, addressee(나 · 특정 인물 …), star_id, sun_id, error_code | 언제 썼는지, 날씨, **위기 글 여부** | title, text, summary, events, addressee_person, past · steps_enc |
| suns | name(기준 축 9개 이름), custom | 삶의 어느 영역에 글이 있는지 | — |
| stars | sun_id | — | 작은 별(주제) 이름 |
| thoughts | kind, certainty, value(가치 보기 값), grateful, position | 생각 종류 · 감사 여부 | text, quote, self_change, topic |
| people | **relation**(엄마 · 선배 …), auto | 어떤 관계의 사람이 등장하는지 | name, nicknames |
| people_questions | reason, answer | — | name |
| relations | type, grp, line, cross_domain, needs_confirm, vow_kept | 관계 종류 | explanation, quote, axis, topic |
| states | key(생각 · 관계 id), kind, state | 다짐 · 질문이 열림 · 지킴 | 전체 이력 |
| aspirations | version, values | 고른 가치 | now, said, obstacle, if_then |
| messages | tone, **mode(care · comfort)**, next_kind | 돌봄 · 위로 응답을 받았는지 | text, next_question |
| feedback | target, target_id, **value**(오늘은 위로만 …) | 그날 상태 버튼 | 불편한 점 한 줄 |
| runs | step, ms, calls, est_usd, error_code, **meta.situations**(무거운 날 …) | 그날 마음 상태 이름 | — |
| profiles | settings, onboarding | 말투 · "오늘은 살살" 날짜 | — |
| Chroma | user_id, entry_id, star_id, written_at, kind + 임베딩(가명 글) | 임베딩에서 대략 뜻을 되살릴 수 있음(이론상) | 문서 없음 |
| 로그(logger) | 경로 · id · 단계 · 비용 · 검사 · 상황 이름 | 상황 이름(무거운 날) | 원문 · 이름 없음(ALLOWED 목록, 40자 자름) |

암호화 방식: AES-256-GCM, 사용자 키 = HKDF-SHA256(마스터, salt=user_id, info 고정), 행마다 무작위 12바이트 nonce, AAD = `표:행 id`(단계 저장값은 `entries.steps:id`). 사용자 키가 다르고 AAD 가 행에 묶여 다른 사용자 · 다른 행으로 옮겨 붙이면 풀리지 않는다. 키는 오류 · 로그에 나가지 않는다(EncryptionKeyMissing 문구에 값 없음, 전역 오류 처리는 예외 이름만 기록). 문제 없음.

## 외부로 나가는 것

- Studio(`studio.run`) 는 guard 밖이면 RuntimeError, 보내기 직전 `m.check(html)`. Solar chat · embed 도 guard 안이면 검사. 그래프의 모든 노드가 `llm.guard(state.people)` 안에서 돈다(코드). 위기 글은 safety 다음 바로 save 로 가서 밖으로 나가지 않는다.
- 한계: guard 는 "등록된 이름"만 안다(M1). 한마디 만들 때 지난 한마디 · 다짐 · 질문 글도 가명으로 함께 보낸다(설계대로).
- 실행 기록 · 오류 응답 · /stats 에 원문 없음(재현함: 원문 넣은 422 응답과 서버 로그에서 원문 문자열 0건). SSE error 이벤트는 코드 · 정해 둔 문구만.

## 입력 검증 · 남용

- 글 8000자 · 제목 120자 · 모르는 칸 거부 · 날씨/말투/가치/피드백 보기 값 검사: 재현함(422).
- 하루 10편(L5 로 우회), 월 $5(H1 · M8 로 우회), 같은 기록 동시 실행 막음(M9 한계).
- SSE: 스트림 하나가 스레드풀 스레드를 10초씩 잡는다. 동시 기록 수가 하루 한도로 묶여 있어 지금 규모에선 문제 아님.
- 사람 · 피드백 · 되고 싶은 모습 추가에는 개수 제한이 없다(자기 계정만 무거워짐, 낮음).

## 화면

- 토큰: supabase-js 기본(localStorage). XSS 길(dangerouslySetInnerHTML · innerHTML · eval · 외부 링크)은 없다.
- 위기 화면: 109(24시간 · 무료 · 문자 가능) `tel:` 링크, 마들랜(카카오톡 · 앱 · 24시간), 112 · 119 안내. v8.json 과 화면 사본이 같다. 내용은 코드 주석상 2026-10-08 보건복지부 안내로 확인됨(이번 검토에서 바깥 확인은 안 함 — 확인 필요).
- 가짜 데이터 모드: `NEXT_PUBLIC_MOCK=1` 은 빌드 때 박힌다. 배포는 git 연결 + Vercel 환경변수 `NEXT_PUBLIC_MOCK=0` · `DEV_LOGIN=0`(deploy/MORNING.md)이라 위험 낮음. 로컬 `infra/frontend/.env.local` 은 DEV_LOGIN=1 이지만 gitignore 라 git 배포에는 안 올라간다. Vercel CLI 로 로컬 폴더를 올리면 따라갈 수 있으니 CLI 배포는 하지 않는다.

## 설정 · 배포

- CORS: 화면 주소 하나, credentials 끔, 인증은 Bearer 헤더 → 문제 없음.
- `.env.example` · `infra/frontend/.env.example` 에 값 없음. `.gitignore` 가 `.env` · `.env.local` · `.env.*.local` · runs · logs 를 뺀다. git 이력에 .env 파일 · 키 모양 문자열 0건.
- `.vercelignore` 가 `/.env*` · `/data` · `/runs` · `/logs` 를, `vercel.json` excludeFiles 가 data · runs · tests · eval 등을, `.dockerignore` 가 `**/.env*` · data · runs · logs 를 뺀다. 백엔드 이미지는 main.py · app 만 복사.
- 계정 삭제: 없음(M3).
- 이번 검토에서 보지 않은 것: 1차 Streamlit 앱(app.py · streamlit_app.py, v8 배포 대상 아님), 클라우드 Supabase · Vercel 실제 설정.

## 고치는 순서 제안

1. H1(Data API 막기 + est_usd check) — 배포 전 필수.
2. M6(허용 이메일 목록), M4(로그아웃), M8(resume 상한), M2(Studio 파일 지우기).
3. M3(DELETE /me), M5(crisis · mode 암호화), M1(이름 후보 넓히기).
4. M7 은 동규 결정(이력 정리 여부).
