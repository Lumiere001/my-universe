# 나의 우주 v8 API 약속 (WS5 백엔드 ↔ WS6 화면)

작성 2026-10-08 밤(오케스트레이터). WS5와 WS6이 동시에 개발할 수 있게 먼저 정한 모양이다. 고칠 때는 두 쪽을 함께 고친다. 실제 문서는 FastAPI가 만드는 `/docs`(OpenAPI)가 최종이다(로컬에서 `API_DOCS=1`일 때만 열림, 배포는 꺼 둠).

**WS5 구현에서 바뀐 점(2026-10-08):** 아래 본문에 반영했다. 요약은 맨 끝 "§7 WS5 구현 메모".

**시험 단계 위기 대응(2026-10-08 아침, 동규 결정):** 위기 글도 7단계를 다 돌고 평소 EntryResult 를 준다. `care` 칸을 없애고 `message.check_in`(안부 한 줄)을 더했다(§1).

**기록 칸(WS11, 2026-10-13):** 쓰기 본문에 `source` · `source_ref` · `day`, EntryResult · 목록에 `source` · `day` · `day_basis` · `day_check` · `confirmed` · `record_type`, 생각에 `original`, `info.original` 을 더했다(칸 추가만). 같은 글(같은 Studio 설정) · 같은 원본이 다시 오면 Studio 를 부르지 않고 그 기록으로 안내한다(§1). 마이그레이션 `20261013000000_v8_record_fields.sql`(덧붙이기만).

**쓰기 화면 작은 묶음(WS13, 2026-10-14):** `GET /diary/prompt`(쓰기 화면 위 별지기 말풍선) · `PATCH /diary/{id}/day`(글이 다루는 날 고치기) 를 더하고(§2), Settings 에 `keeper_name`(별지기 이름)을 더했다(§6). 새 경로 · 칸 추가만이고 마이그레이션은 없다.

**대화 · 요약 확인(WS19 · WS20, 2026-10-14):** `/talk` 경로 묶음(§8)과 `POST /diary/{id}/confirm`을 더했다. 쓰기 본문에 `confirm`(기본 false), EntryResult `status`에 `confirm`(확인을 기다리는 초안 — DB 의 status 는 그대로 processing)을 더했다(칸 · 값 추가만, 텍스트 길은 그대로). 마이그레이션 `20261014000100_v8_conversations.sql`(새 표만).

**관측 보고서 · JSON 내려받기(WS15, 2026-10-14):** EntryResult 에 `observation`(관측 상태 · 한계)을 더하고(§1), `GET /export` · `GET /export/{id}`(JSON 내려받기)를 더했다(§2.1). 다른 사람 이름은 가리지 않는다(2026-10-13 동규 결정 12). 칸 · 경로 추가만이고 마이그레이션은 없다.

**사진(손글씨) 입력(WS18, 2026-10-14):** `POST /photo/read`(사진 한 장의 글자만 읽기, 저장 안 함)를 더했다(§1.1). 읽은 글은 지금의 쓰기 본문(`source: "사진"`)으로 보낸다. 새 경로만이고 마이그레이션 · 새 환경변수는 없다(기존 `UPSTAGE_API_KEY`).

**사진 글자 읽기 모델 → Document Parse(2026-10-28 동규 결정):** `POST /photo/read` 의 모양 · 오류는 그대로이고 읽는 모델만 `document-parse` 로 바꿨다(§1.1). 되돌리기용 선택 환경변수 `PHOTO_READ_MODEL`(`document-parse` 기본 | `ocr`)을 더했다. 보내는 곳(Upstage Document Digitization)은 같다.

**인스타 ZIP 가져오기(WS17, 2026-10-14):** `POST /import/instagram/preview`(저장 · 외부 전송 없는 미리 보기)를 더했다(§9). 가져온 글은 기존 `/diary/stream` 에 `source: "지난 글 묶음"` · `source_ref` · `written_at`(게시 시각)으로 한 편씩 보낸다. 새 경로만이고 마이그레이션은 없다.

**말로 쓰기 · 읽어 주기(WS21, 2026-10-14):** `POST /voice/transcribe`(녹음 받아쓰기, 저장 안 함) · `POST /voice/speak`(별지기 말 mp3)를 더하고(§10), 대화 턴 본문에 `via`(text · voice)를 더했다. 새 경로 · 칸 추가만이고 마이그레이션은 없다(새 환경변수 `ELEVENLABS_*` · `VOICE_MAX_BYTES`).

**꾸미기(WS25, 2026-10-14):** Settings 에 `theme`(우주 테마) · `keeper_look`(별지기 모습)을 더했다(§6). 기본값은 예전 모습이고 화면에만 쓴다. 새 경로 · 마이그레이션 없음.

**보안 검토 반영(2026-10-09, docs/security-review-v8.md):** 허용 이메일 목록(403 `not_allowed`), `DELETE /me`(계정과 모든 기록 지우기), 이어 하기 상한(429 `resume_limit` · 비용 · 하루 수), 실행 잠금을 DB 로, `/docs` 끔, Data API(/rest/v1) 닫음. 허용 목록 · 상한은 환경변수를 설정했을 때만 건다 — 지금 배포는 둘 다 설정하지 않는다(2026-10-08 아침 동규: 구글 로그인한 누구나 · 상한 없음, plan §2-9).

## 0. 공통

- 백엔드: FastAPI(`main.py`), 로컬 · Docker는 `http://localhost:8001`, 배포는 Vercel(Python 함수). 화면은 `NEXT_PUBLIC_API_BASE`로 주소를 받는다. 백엔드는 `FRONTEND_ORIGIN`만 CORS 허용.
- 로그인: Supabase Auth. 화면이 받은 access token을 모든 요청에 `Authorization: Bearer <token>`으로 보낸다(`/health` · `/ontology` 제외). 백엔드는 토큰을 Supabase(`/auth/v1/user`)로 확인해 user id를 얻는다.
  - 배포: 구글 로그인(`supabase.auth.signInWithOAuth({ provider: "google" })`). 구글 OAuth 키는 동규가 아침에 넣는다.
  - 로컬: `NEXT_PUBLIC_DEV_LOGIN=1`일 때만 시험용 계정(이메일 · 비밀번호, 로컬 Supabase에만 있음) 로그인 칸을 보인다.
  - 초대 목록(설정했을 때만): 백엔드 환경변수 `ALLOWED_EMAILS`(쉼표 목록)가 있으면 목록 밖 계정은 모든 로그인 요청이 403 `not_allowed`("초대된 사람만 쓸 수 있어요"). 화면은 이때 안내와 로그아웃만 보인다. 없으면 로그인한 누구나(지금 배포, 2026-10-08).
  - 화면(supabase-js)은 로그인에만 쓴다. Supabase Data API(`/rest/v1` · GraphQL)로는 표를 읽고 쓸 수 없다(anon · authenticated 권한 없음). 데이터는 모두 이 API로.
- 오류: HTTP 상태 + `{"error": {"code": "영문_코드", "message": "한국어 안내"}}`. 코드: `unauthorized`(401) · `not_allowed`(403, 초대 목록 밖 — `ALLOWED_EMAILS`를 설정했을 때만) · `invalid_input`(422, 틀린 칸 이름만 알림, 입력값은 되돌려 보내지 않음. 경로의 id 가 영문 · 숫자 · `_` · `-` 가 아니어도 422) · `not_found`(404) · `already_running`(409) · `duplicate`(409, `POST /diary` 에 이미 받은 글이 정리 중이거나 멈춤) · `invalid_target`(409, 버튼을 누를 수 없는 대상) · `fact_bomb_ack_required`(409) · `daily_limit`(429, 사용자별 하루 처리 글 수 `DAILY_ENTRY_LIMIT`를 설정했을 때만) · `monthly_budget`(429, 사용자별 이번 달 추정 비용 `MONTHLY_COST_CAP_USD`를 설정했을 때만) · `resume_limit`(429, 기록 하나당 이어 하기 `RESUME_LIMIT`를 설정했을 때만. 셋 다 기본 0 = 상한 없음) · `account_delete_failed`(502) · `auth_unavailable` · `db_unconfigured` · `account_delete_unconfigured` · `vector_delete_failed`(503) · `internal`(500).
- 동의(WS24, §6.1): 지금 판에 동의하지 않은 사용자의 기록 만들기(`POST /diary` · `/diary/stream` · 이어 하기)는 403 `consent_required`. 읽기 · 지우기 · `/me` · 설정 · 계정 지우기는 동의 없이도 된다.
- 입력 글의 NUL 등 제어 문자(줄바꿈 · 탭 제외)는 받을 때 지운다.
- 시각은 ISO 8601(+09:00). id는 문자열.
- 원문(일기 글 · 인용 · 사람 이름)은 실행 기록 · 오류 메시지 · `/stats`에 절대 넣지 않는다.

## 1. 일기 쓰기 (SSE)

`POST /diary/stream` 본문 `{"text": "...", "title": "선택", "written_at": "선택, 없으면 지금", "weather": "맑음|구름 조금|흐림|비|천둥|안개|null", "source": "텍스트(기본)|사진|지난 글 묶음|대화", "source_ref": "선택, 가져온 원본 표시(게시물 시각 · 파일 이름 등)", "day": "선택, 사용자가 고른 글이 다루는 날 YYYY-MM-DD"}`

입력 검사: `text` 1~8000자(`MAX_TEXT_CHARS`), `title` 120자까지(줄바꿈은 띄어쓰기로), `weather`는 v8.json 보기만, `source`는 네 값만, `source_ref` 200자까지, 모르는 칸은 거부(422).

- **글이 다루는 날(`day` · `day_basis`, PRD §4.4 · G2):** `day`를 주면 그날(확실). 없으면 제목 → 본문 첫 줄(30자 이하일 때만) 속 날짜(`3/27` · `3.27` · `3월 27일` · `2026.3.27` · `260327` …, 연도가 없으면 쓴 날과 같거나 앞선 가장 최근 해 — 10월에 쓴 `3/27`은 올해 3월, 1월에 쓴 `12/31`은 지난해)를 읽어 확실. 날짜처럼 보이는데 못 읽거나(13/45 · 2/30) 서로 다른 날짜가 둘 이상이면 쓴 날 · 추정 + `day_check: true`('날짜 확인 필요'). 날짜가 없으면 쓴 날 · 추정. `source: "대화"`는 대화한 날 · 확실 + `confirmed: "확인 전"`.
- **같은 글 다시 보내지 않기(PRD §8.5 A, 상한이 아니라 중복 막기):** 사용자별 HMAC(띄어쓰기 · 줄바꿈 차이를 없앤 제목 · 본문 + 쓴 날(한국 시간 날짜) + Studio 설정 번호)을 `entries.content_hash`에 둔다. 같은 날 쓴 같은 글이 다시 오면(다른 날 쓴 똑같은 짧은 글은 새 기록)(또는 같은 `source`의 같은 `source_ref`) 새 기록을 만들지 않고 Studio · Solar 를 부르지 않는다. 그 기록이 끝났으면 `event: result`로 그 기록의 EntryResult + `"duplicate": true`(progress 없음), 끝나지 않았으면 `event: error` `{"entry_id": 그 기록, "code": "duplicate", "resumable": true}`(→ 이어 하기). 그 기록이 실명 새어 나감(`real_name_leak`)으로 멈췄으면 `"resumable": false`(이어 하기를 권하지 않음). `POST /diary`는 같은 결과 또는 409 `duplicate`. 설정 번호가 바뀌면 같은 글도 새로 정리한다. `source_ref`는 평문으로 두지 않고 HMAC 으로 저장한다(사용자별 유일, 같은 원본을 동시에 두 번 보내 DB 가 뒤의 것을 막아도 500 이 아니라 같은 duplicate 응답).

응답 `text/event-stream`. 화면은 `fetch` + `response.body.getReader()`로 읽는다(EventSource는 POST · 헤더를 못 씀).

```
event: progress
data: {"entry_id": "e1", "step": "safety", "label": "글을 살펴보는 중", "done": 1, "total": 7}

: keep-alive            ← 약 10초마다 (주석 줄, 무시)

event: result
data: {EntryResult}

event: error
data: {"entry_id": "e1", "code": "studio_timeout", "message": "...", "resumable": true}
```

- step 순서: `safety`(위기 확인) → `names`(사람 · 가명) → `record`(기록 Agent) → `past`(지난 생각 고르기) → `observe`(관측 Agent) → `voice`(한마디) → `save`. 위기 글도 같다(시험 단계).
- 끊기면: `GET /diary/{id}`로 상태를 보고, `status`가 `failed`이거나 멈춰 있으면 `POST /diary/{id}/resume/stream`(같은 이벤트, 끝난 단계는 건너뜀 — 건너뛴 단계도 progress 는 다시 보낸다). 화면이 끊겨도 서버(로컬 · Docker)는 끝까지 처리한다. 서버가 다시 켜져 멈춘 기록은 `GET /diary/{id}`가 `failed`로 알려 준다.
- `error` 이벤트의 `resumable`: 실명 검사에 걸린 경우(`real_name_leak`, 밖으로 보내지 않음)만 `false`. 그 밖의 코드: `studio_timeout` · `studio_failed` · `studio_bad_output` · `llm_failed` · `internal`.
- 한 기록을 동시에 두 번 돌리지 않는다(409 `already_running`). 잠금은 DB(`entries.locked_until`, 조건부 update)라 서버 인스턴스가 여러 개여도 하나만 돈다. 노드가 끝날 때마다 잠금을 `RUN_LOCK_S`(기본 600초)만큼 늘리고, 끝나면 푼다. 서버가 멈춰 잠금이 만료되면 `GET /diary/{id}`가 `failed`로 알려 준다.
- 운영 상한은 환경변수를 설정했을 때만 건다(기본 0 = 없음). 설정하면 이어 하기도 이번 달 비용 상한(`monthly_budget`)과 하루 수를 본다. 하루 수 = 오늘 처리를 시작하거나 이어 한 기록 수(오늘 이미 센 기록을 다시 이어 하는 건 더하지 않음, 지운 글도 그대로 셈, 시드한 글은 안 셈). 기록 하나당 이어 하기는 `RESUME_LIMIT`번까지(429 `resume_limit`).
- 시험 · curl용으로 같은 본문의 `POST /diary`(스트림 없이 EntryResult 한 번)도 둔다.

## 1.1 사진 글자 읽기 (WS18, 2026-10-14)

`POST /photo/read` 본문 = 사진 한 장의 바이트 그대로(multipart 아님, `Content-Type` 은 아무거나 — 형식은 앞 바이트로 본다) → `{"text": "읽은 글(줄 단위, 빈 줄 뺌, 글자가 없으면 \"\")"}`.

- 흐름(PRD §3 손글씨 사진, 결정 5): 화면이 사진을 긴 변 2400px JPEG 로 다시 그려 4MB 아래로 줄이고(위치 정보 등 메타데이터도 빠짐) 한 장씩 부른다 → 읽은 글을 쪽 순서대로 쓰기 칸에 채움 → 사용자가 고침 → `POST /diary/stream` 에 `"source": "사진"`. 그 뒤는 텍스트와 같은 길(위기 판정 · 가명 처리 → 기록 · 관측 · 한마디). 글이 다루는 날은 첫 줄 날짜(G2, 확실), 없으면 올린 날 · 추정.
- 여러 쪽: 한 요청 = 한 장(Vercel 함수 요청 본문 4.5MB 한도). 화면이 순서대로 부르고 줄바꿈으로 이어 붙인다.
- 저장하지 않는다: 사진은 이 요청의 메모리에서 Upstage Document Digitization(기본 `model=document-parse`, 아래 '모델')으로 보내고 버린다. DB · 디스크 · 실행 기록에 사진 · 읽은 글이 남지 않는다(기록에는 `upstage_ocr` · 모델 이름 · 쪽 수 · 추정 비용 · 시간만). `ocr` 응답은 `stored: false`(2026-10-14 확인), `document-parse` 동기 응답에는 그 칸이 없다(2026-10-28 확인 — Upstage 쪽 보관은 개인정보처리방침대로 '확인 중').
- 이름 가리기 예외(결정 7): 사진 속 이름은 가릴 수 없어 그대로 간다(개인정보처리방침 · 첫 사용 동의에 밝힘). 정리 · 대화 요청의 실명 0건 관문은 고친 글을 보낼 때 그대로 건다.
- 입력 검사(신뢰 경계, 운영 상한 아님): jpg(`FF D8 FF`) · png · heic(`ftyp` heic · heix · hevc · hevx · heim · heis · mif1 · msf1)만. 크롬은 HEIC 를 못 그려서 화면이 4MB 아래 HEIC 는 그대로 보낸다(Upstage 가 읽음).
- 오류: 403 `consent_required`(동의 전 — 사진이 밖으로 나가기 전에 막음) · 413 `photo_too_big`(4.5MB 넘음, 받는 중에 멈춤) · 415 `photo_type` · 422 `photo_empty` · 502 `ocr_busy`(Upstage 429 를 1.5초 쉬고 두 번 더 물어도 붐빔) · 502 `ocr_failed` · 503 `ocr_unconfigured`(`UPSTAGE_API_KEY` 없음, 또는 `PHOTO_READ_MODEL` 이 모르는 값).
- 모델: `document-parse`(standard 모드, 쪽당 $0.01, 2026-10-28 동규 결정). 폼 `ocr=force` · `output_formats=["html", "text"]`. 되돌리려면 환경변수 `PHOTO_READ_MODEL=ocr`(쪽당 $0.0015, 코드 안 고침).
  - 줄 공책은 Document Parse 가 **표 하나**로 읽는다(줄 = 행, 왼쪽 여백 = 빈 칸, 아래 빈 행). 응답 `content.text` 는 마크다운 표(`|  | 글 |`, `| --- |`)라 그대로 쓰면 글자 정확도가 떨어진다(10-14 의 0.35 가 이것 — 글자는 맞게 읽었음). 그래서 요소를 응답 순서대로 이어 붙이되 표는 `html` 을 행마다 한 줄(칸은 빈칸으로 이음, 빈 행 뺌)로 풀고, `footer`(쪽 번호 등)는 빼고, `header` 는 남긴다(공책 위 날짜 칸이 머리말로 읽혀도 G2 날짜를 잃지 않게) — `app/service/ocr.py` `dp_text`.
  - 2026-10-28 가상 손글씨 4장(`tests/fixtures/photos`, `tools/photo_samples.py measure`, 모델 `document-parse-260930`) 글자 정확도(띄어쓰기 무시): ocr 1.0 · 1.0 · 0.981 · 1.0(약 1.5초), DP 그대로 0.346 · 0.203 · 0.481 · 0.346, DP 풀기 1.0 · 1.0 · 0.981 · 1.0(약 2.5초, 첫 장 3.6초). 0.981 은 두 모델 모두 '알람'을 '일람'으로 읽은 것. enhanced 모드(쪽당 $0.03)는 표 없이 문단으로 읽어 1.0 이지만 standard + 풀기와 같아 쓰지 않는다.
  - 글자 읽기 비용은 `runs` 표(이번 달 추정 비용)에 들어가지 않는다(기록이 생기기 전이라) — 실행 기록(`what: upstage_ocr`)의 `est_usd` 로 센다.

### EntryResult

```json
{
  "id": "e1", "status": "processing|done|failed", "step": "observe",
  "written_at": "2026-10-09T23:10:00+09:00", "title": "...", "weather": "흐림",
  "crisis": false,
  "source": "대화|텍스트|사진|지난 글 묶음", "day": "2026-10-09", "day_basis": "확실|추정", "day_check": false,
  "confirmed": "확인 전|확인됨|null", "record_type": "경험 기록|생각·성찰|창작|기타|null",
  "info": {"summary": "...", "addressee": "나|특정 인물|신|기타", "addressee_person": "p1|null", "events": ["..."],
           "original": {"addressee": "목록 밖 원래 말", "record_type": "목록 밖 원래 말"} },
  "thoughts": [
    {"id": "t1", "text": "...", "kind": "다짐", "grateful": false, "certainty": "단정",
     "value": "성취|null", "quote": "원문 그대로", "self_change": "스스로 쓴 변화|null",
     "topic": "작은 별 이름", "star_id": "s1", "sun_id": "d1", "people": ["p1"],
     "other": "목록 밖 원래 말|null", "original": {"kind": "...", "certainty": "...", "value": "..."},
     "state": {"type": "다짐|질문|긴장|바뀜", "status": "열림|지켜짐|그만둠|해소|블랙홀|후보|확정", "mistake": false} }
  ],
  "relations": [
    {"id": "r1", "from": "t1", "to": "t9", "from_entry": "e1", "to_entry": "e0",
     "type": "이어짐", "group": "판단형|영향형", "line": "실선|점선", "cross_domain": false,
     "needs_confirm": true, "explanation": "...", "quote": "원문|null"}
  ],
  "past": [{"thought_id": "t9", "entry_id": "e0", "text": "...", "written_at": "..."}],
  "reached": [{"aspiration_id": "a1", "quote": "...", "message": "..."}],
  "message": {"text": "...", "tone": "다정하게", "mode": "normal|comfort", "check_in": "안부 한 줄|null"},
  "next_question": {"kind": "weather|aspiration|free|none", "text": "..."},
  "people_questions": [{"id": "q1", "name": "...", "question": "...", "options": ["..."]}],
  "observation": {"state": "해소|바뀜|긴장|어긋남|이어짐|목표 충돌|이어진 지난 생각 없음|처음 쓰는 주제|비교할 지난 글 없음|생각이 없는 글",
                  "limits": ["생각 나누기와 이어진 선은 AI 가 원문 인용을 근거로 한 추정이라 틀릴 수 있어요.", "..."]}
}
```

관측 보고서(WS15, PRD §7 474): `observation` 은 끝난 기록에만(그 밖은 null). `state` 는 규칙이 거른 뒤 저장된 관계로 다시 센다(관측 Agent 의 Classify 는 저장하지 않음): 생각이 없으면 `생각이 없는 글`, 정리할 때 비교한 지난 생각이 없으면 `비교할 지난 글 없음`, 이 글이 새 쪽인 지난 글과의 관계가 있으면 그 종류 중 앞의 것(해소 > 바뀜 > 긴장 > 어긋남 > 이어짐, 목록 밖 `목표 충돌`은 그 뒤 — v8.json `observation_states.priority`), 관계가 없고 같은 작은 별의 지난 생각이 있었으면 `이어진 지난 생각 없음`, 아니면 `처음 쓰는 주제`. 같은 글 안의 관계는 세지 않는다. `limits` 는 그 기록에 맞는 한계 문장: AI 추정(생각이 있으면 늘) · 비교한 지난 생각 수와 고른 방법 · 점선이 있으면 확인 부탁 · 날짜 확인 필요 또는 날 추정.

기록 칸: `source` 출처, `day` 글이 다루는 날(이 칸 전에 저장된 기록은 쓴 날 · 추정), `day_check` 날짜 확인 필요(G2), `confirmed` 대화에서 온 글의 요약 확인 상태(그 밖은 null), `record_type` 기록 Agent Classify 가 고른 글 유형(목록 밖이면 `기타` + `info.original.record_type`, 이 칸 전 기록은 null). `thoughts[].original` 은 목록 밖 값의 원래 말(종류 · 확신 · 가치, 없으면 null). `other` 는 예전 화면용으로 종류의 원래 말만.

`crisis`: 위기로 감지된 글이면 true(감지 결과는 기록 enc 안에 남겨 얼마나 자주 걸리는지 본다). 시험 단계(2026-10-08 아침 동규 결정)에는 위기여도 결과 모양이 같다 — `care` 칸은 없앴고(돌봄 화면 · 109 · 마들랜 · 119 · 112 안내 없음), 생각 · 관계 · 우주 행성이 평소처럼 나온다(Studio · Solar 도 평소처럼, 가명 글로). 위기 글의 `message`는 `mode: "comfort"`(제안 · 다음 질문 없음, 팩폭이면 그 글만 `tone: "다정하게"`)이고, `message.check_in`에 안부 한 줄(코드에 둔 고정 문장, 지난 안부와 겹치지 않게)이 온다. 화면은 한마디 아래 작은 줄로 보인다. 위기 2차 판정(Solar)이 실패한 글은 평소 `message` + 같은 `check_in`. 그 밖의 글은 `check_in: null`. 정식 운영 때의 안내(v8.json `crisis.resources`)는 그때 다시 정한다.

그 밖의 칸: `thoughts[].state` 는 그 생각의 다짐 · 질문 상태, 없으면 그 생각이 새 쪽인 바뀜, 없으면 그 생각이 낀 긴장(`열림|블랙홀|해소`). `relations` 는 이 기록이 새 쪽(`to_entry`)인 관계 + 이 기록에서 시작해 뒤 기록으로 이어진 관계. `people_questions[].options`: 동명이인 · 별명은 `["같은 사람", "다른 사람", "사람 이름 아님"]`, 이름인지 낱말인지는 `["사람 이름", "사람 이름 아님"]`. `next_question.kind`: voice 의 weather → `weather`, aspiration · aspiration_invite → `aspiration`, first · commitment · open_question · widen(좁아짐 막기: 오래 비어 있는 해 · 글이 없는 기준 축을 가끔 묻기) → `free`, 없음 → `none`.

## 2. 읽기

- `GET /diary?limit=20&before=<written_at>` → `{"entries": [{"id", "written_at", "title", "summary", "weather", "status", "sun", "star", "source", "day", "day_basis", "day_check", "confirmed", "record_type"}]}`
  쓴 시각(`written_at`) 내림차순, `before` 를 주면 그보다 앞에 쓴 것만. `limit` 기본 20, 1~500(넘으면 422). 지난 기록 화면(달력 · 찾기 · 주제별)과 사이드바 작은 달력은 `limit=500` 으로 모두 읽고, 500편이 꽉 차면 마지막 `written_at` 을 `before` 로 이어 읽는다(2026-10-28). 달력은 글이 다루는 날(`day`, 평문 칸 · 비어 있던 옛 행은 쓴 날의 한국 날짜)로 놓으므로, 쓴 시각으로 나눈 쪽 대신 전체를 받는 쪽을 골랐다(`since`/`until` 날짜 거르기는 `day` 가 빈 옛 행 때문에 쓴 시각 거르기와 어긋나 두지 않음). 확인 전 대화 초안은 빠진다(§8).
- `GET /diary/{id}` → EntryResult
- `DELETE /diary/{id}` → 204 (생각 · 관계 · 한마디 · 그 기록 · 생각 · 관계를 가리킨 피드백 · 벡터까지. 남은 기록이 모두 끝난 상태면 이 기록에만 쓰인 작은 별 · 자동 등록 사람도 정리). 정리 중이면 409.
- `GET /diary/prompt` → `{"kind": "first|weather|aspiration|free|none", "text": "질문", "vow": {"thought_id", "text", "overdue": false} | null}` 쓰기 화면 위 별지기 말풍선(LLM 없음). 기록이 없으면 정해 둔 첫 만남 질문(`first`, PRD §6.2), 있으면 마지막 글의 '다음에 써 볼 질문'(`next_question` 과 같은 종류 · 글). 날씨 질문은 건너뛰었으면(`weather_ask: false`) `none`, 되고 싶은 모습 질문은 넘어감 · 그만 묻기 · 이미 적었으면 `none`. `vow` 는 다짐 안부: 기한이 지났거나(`overdue: true`) 마지막 글에서 나온 열린 다짐 하나(화면은 지켰어요 · 그만둘래요 버튼, 누르면 닫혀 다시 안 나옴). 마지막 글이 위로 모드(무거운 날 · 위기)였거나 오늘은 위로만이면, 또는 지난 질문이 이미 다짐 안부면 `null`. `/diary/{id}` 보다 먼저 등록한다.
- `PATCH /diary/{id}/day` `{"day": "YYYY-MM-DD"}` → EntryResult. 글이 다루는 날을 고친다(`day_basis: "확실"`, `day_check: false`). 정리 결과(생각 · 관계)는 다시 돌리지 않는다. 정리 중이면 409 `already_running`, 남의 · 없는 기록은 404.
- `GET /universe` → 아래 Universe
- **작은 별 묶음(2026-10-29, `rules.groups`):** 새 작은 별이 생긴 글이 끝나면(그래프 `group_stars`) 쌓인 작은 별 전체를 Solar 가 같은 고민끼리 묶고(①) 묶음마다 해를 고른다(②). 작은 별은 지우지 않고 별 enc 에 묶음 머리(`group`)만 적는다. `/universe` · `/insight` · `/diary` · `/diary/{id}` · `/export` 의 작은 별(`star`, `topic`, `star_id`)은 **묶음 머리**로 나온다. 묶기는 관측 전에 돌아 지난 생각 고르기 · 관측 Agent · 관계 규칙(판단형은 같은 주제 안)도 묶음 단위로 본다. 기록 Agent 에게는 작은 별 이름 전체를 준다. 묶음의 해로 별 · 생각 · 기록의 해를 옮긴다(사용자가 옮긴 별 `pin` 은 그대로). `PATCH /stars/{id}`(해 옮기기) · `POST /stars/merge` 는 묶음 전체에 적용, 거절한 합치기 짝은 같은 묶음에 넣지 않는다. 모드를 바꾼 뒤(`ONTOLOGY_PROFILE`) 처음 `/universe` · `/insight` 를 열면 한 번 다시 묶는다(기존 해 옮기기). `STAR_GROUPS=0` 이면 끔. **일관성(2026-10-30):** 다시 묶을 때 지난 묶음 번호를 함께 보내 분명할 때만 나누고, 지난 묶음끼리는 합치지 않는다(코드로도 막음, `keep_old_apart`). 작은 별이 지난번 새로 묶었을 때의 1.5배가 되면 그때만 처음부터 새로 묶는다(설정 `groups_fresh_at`). 해는 매번 다시 고른다.
- `GET /insight`(2026-10-29) → 나에 대해 알게 된 것. 끝난 기록의 생각 · 남은 관계를 코드가 묶는다(AI 요약 · 판정 없음, 원문 인용과 날짜만):
  `{"period": {"from", "to", "records"}, "suns": [{"name", "records", "stars": [{"name", "records", "first", "last", "kinds"}], "kept": [{"star", "times", "from", "to"}], "changed": [Pair], "open": [Pair], "settled": [Pair]}], "across": [{"type", "suns", "from", "to"}]}`.
  Pair = `{"star", "line", "from": End, "to": End, "axis"?}`, End = `{"day", "quote", "record_id", "thought_id"}`. kept = 이어짐(작은 별마다 처음 · 마지막), changed = 바뀜, open = 해소가 붙지 않은 긴장, settled = 해소, across = 해를 넘는 관계. 두 영역 모드의 '그 밖'은 빠진다. 기록이 없으면 `{"period": null, "suns": [], "across": []}`.

### 2.1 JSON 내려받기 (WS15, 2026-10-14)

- `GET /export` → 전체(먼저 쓴 기록부터), `GET /export/{id}` → 기록 하나(남의 · 없는 기록은 404). 화면이 받아 파일(`my-universe-….json`)로 저장한다.
- 모양(`schema: "my-universe-export/1"`):

```json
{
  "schema": "my-universe-export/1", "exported_at": "2026-10-14T21:00:00+09:00", "scope": "entry|all",
  "records": [{EntryResult 에서 people_questions · step 을 뺀 것, "text": "원문 본문",
               "thoughts": [{… EntryResult 의 생각, "domain": "해 이름", "people": ["민준"]}],
               "info": {…, "addressee_person": "이름|null"}}],
  "domains": [{"id": "d1", "name": "건강", "custom": false, "topics": [{"id": "s1", "name": "아침 걷기"}]}]
}
```

- 담기는 것: 기록(원문 · 제목 · 기록 칸 `source` · `day` · `day_basis` · `day_check` · `confirmed` · `record_type`) · 생각 · 영역(`domains` = 해, `topics` = 작은 별, 내보낸 생각이 가리키는 것만 — 전체면 사용자가 더한 해도) · 관계(`relations`) · 보고서(`observation` · `past` · `reached` · `message` · `next_question`).
- **다른 사람 이름은 가리지 않는다**(2026-10-13 동규 결정 12: 본인 기록이라 실명 그대로, 가리기 선택지도 없음). 사람은 id 대신 이름으로 적고(`thoughts[].people` · `info.addressee_person`), 사람 목록(외부 AI 로 보낼 때 가명을 만드는 표)은 넣지 않는다.
- `GET /ontology` → `app/core/ontology/v8.json` 그대로(범례 · 보기 목록은 화면이 여기서 읽는다)

### Universe

```json
{
  "suns": [{"id": "d1", "name": "관계", "custom": false, "planet_count": 3}],
  "stars": [{"id": "s1", "sun_id": "d1", "name": "룸메이트와의 거리", "planet_count": 2}],
  "planets": [{"id": "e1", "star_id": "s1", "sun_id": "d1", "written_at": "...", "title": "...",
               "order": 0, "ring": true, "ring_state": "열림|채워짐|null", "people": ["p1"], "weather": "비",
               "thought_count": 3, "certainty": "단정", "has_question": false}],
  "links": [{"id": "r1", "from_planet": "e1", "to_planet": "e0", "type": "긴장", "line": "점선",
             "cross_domain": true, "needs_confirm": true, "explanation": "...", "ended": false,
             "from_quote": "그때 원문 인용", "to_quote": "지금 원문 인용"}],
  "twins": [{"id": "w1", "a_planet": "e1", "b_planet": "e3", "topic": "...", "status": "열림|해소"}],
  "blackholes": [{"id": "b1", "star_id": "s1", "label": "...", "size": 3, "planets": ["e1", "e3", "e5"]}],
  "north_star": {"text": "...", "values": ["배려"], "reached_planets": ["e3"],
                 "reached": [{"entry_id": "e3", "quote": "...", "at": "..."}]} ,
  "people": [{"id": "p1", "name": "...", "relation": "룸메이트", "planets": ["e1"]}]
}
```

- `order`: 같은 작은 별에서 먼저 쓴 기록이 0(작은 별에 가장 가까움).
- `cross_domain: true`인 선은 화면에서 행성을 눌렀을 때만 그린다(설정 `cross_links`로 정도 조절).
- `north_star`는 되고 싶은 모습이 없으면 `null`. `reached_planets`: 지금 판에 닿은 순간이 있는 행성, `reached`: 그 닿은 순간(원문 인용 · 때, 오래된 것부터 — 북극성을 누르면 나오는 목록).
- `links[].from_quote` · `to_quote`: 선 양 끝 생각의 원문 인용(그때 → 지금, 행성 카드).
- `thought_count`: 생각 수(행성 크기), `certainty`: 가장 많은 확신(같으면 단정, 밝기), `has_question`: 열린 질문이 있음('?'), `ring`: 다짐이 있음, `ring_state`: `열림`(빈 고리) · `채워짐`(지킨 다짐).
- 생각이 없는 글(생각 없이 일정만 적은 글, 시험 단계 전에 저장된 위기 글)은 행성으로 띄우지 않고 `/diary` 목록에만 있다. 같은 기록 안의 관계는 `links`에 넣지 않는다.
- `links[].ended`: 목표 충돌인데 두 다짐 중 하나가 닫힘(지켜짐 · 그만둠) → 충돌이 끝남(화면은 흐리게 그리거나 숨김). 다른 종류는 늘 `false`.
- `explanation`(관계 · 닿은 순간)과 기록 요약에는 사람 판정 · 진단 문장(G3)과 관측 입력의 내부 번호(T1 · P3)가 없다(번호는 '오늘 생각' · '지난 생각'으로 바뀜, 글쓴이 원문에 있는 글자 — 예: 'T1 경기' — 는 그대로 둠).
- `twins` id = 긴장 묶음 키(`긴장:<관계 id>`), `blackholes` 는 풀리지 않은 채 다른 날 다시 나온 긴장.

## 3. 피드백 · 상태 버튼

`POST /feedback` `{"target": "relation|message|vow|question|tension|entry|app|weather", "target_id": "r1|null", "value": "맞아요|아니에요|좋아요|별로|오늘은 위로만|지켰어요|그만둘래요|불편한 점 한 줄|오늘은 살살|날씨 건너뜀", "text": "불편한 점 한 줄일 때만(500자), 그때는 꼭 — 보이는 글자가 없으면 422 invalid_input"}` → `{"ok": true, "state": {"type", "status", "mistake"} 또는 null}`

- 맞아요/아니에요(`target_id` = 관계 id `옛생각id>새생각id`) → 점선을 실선으로 확인(바뀜 후보면 확정) / 관계 지우기, 지켰어요/그만둘래요(`target_id` = 다짐 생각 id) → 닫힘, 오늘은 살살 · 오늘은 위로만 → 오늘 하루 설정(`gentle_today` · `comfort_only_today` = 오늘 날짜), 날씨 건너뜀 → `weather_ask: false`(다음엔 날씨를 묻지 않음). 맞지 않는 대상(이미 닫힌 다짐 등)이면 409 `invalid_target`. 모든 피드백은 맞춤 신호로 저장(불편한 점 한 줄의 글만 암호화). 실행 기록(runs)에는 그때의 Studio 설정 번호 `studio_config`('기록 판/관측 판', 예 `2/2`)를, 피드백에는 누른 때가 아니라 그 대상(기록 · 생각 · 관계)의 기록을 처리한 마지막 실행의 설정 번호를 남긴다(기록과 상관없는 피드백은 null). '아니에요'로 지운 관계는 종류 · 두 생각 id 를 그 피드백의 암호문에 남긴다(오답 재료, 기록을 지우면 같이 지움).

## 4. 사람

- `GET /people` → `{"people": [{"id", "name", "nickname", "relation", "auto": true, "planets": ["e1"], "forget_as": "선배"}]}`. `forget_as`: 지우면 이름 자리에 들어갈 말(2026-10-28) — 이름 · 별명이 가족을 부르는 말이면 묶음 말(엄마 · 어머니 · 어머님 · 아빠 · 아버지 · 아버님 → 부모, 할머니 · 할아버지 → 조부모, 형 · 오빠 · 누나 · 언니 · 동생 · 남동생 · 여동생 → 형제자매), 아니면 관계 말, 관계가 비었거나 이름과 같으면 `그 사람`(`app/service/safety/pseudonym.forget_word`).
- `POST /people` `{"name", "nickname", "relation"}` · `PATCH /people/{id}` · `DELETE /people/{id}`(지우기 = 저장된 글에서 이름을 `forget_as` 로 바꾸고 문장은 남김) → `{"ok": true, "replaced": 4}`
- `POST /people/questions/{id}` `{"answer": "같은 사람|다른 사람|사람 이름|사람 이름 아님"}` → `{"ok": true}`. 다른 사람 · 사람 이름 → 사람 목록에 더함, 같은 사람(별명) → 겹치는 사람의 별명으로 더함.
- `GET /people/{id}/thoughts` → `{"person": {"id", "name", "relation"}, "thoughts": [Thought + {"entry_id", "written_at", "title"}]}`: 그 사람과 얽힌 생각(끝난 기록만), 먼저 쓴 기록부터 · 같은 기록 안은 글 순서. 우주에서 사람을 고르면 나오는 목록. 없는(남의) 사람이면 404.
- `nickname`은 쉼표로 여러 개. 새 이름은 글을 쓸 때 자동 등록(`auto: true`)된다(가명으로 보내기 위해). 손으로 고치면 `auto: false`.
- `DELETE /people/{id}/with-thoughts` → `{"ok": true, "replaced": 4, "hidden": 3}`: 사람 지우기 + **그 사람이 나온 생각도 숨기기**(WS16). 그 사람이 나온 생각 · 그 생각의 관계 · 상태 · 닿은 순간 · 피드백 · 벡터를 지우고, 글 본문은 `DELETE /people/{id}` 처럼 이름만 관계 말로 바꾼다. 순서: 벡터 → DB(벡터를 못 지우면 503 `vector_delete_failed`, 아무것도 안 지움). 정리 중인 기록이 있으면 409 `already_running`.

## 4.1 우주 고치기 (WS16, 2026-10-14)

`app/api/edit.py` · `app/repository/edit.py`. 남의 해 · 별 · 생각이면 404. 작은 별 옮기기 · 합치기 · 사람과 생각 지우기는 정리 중인 기록이 있으면 409 `already_running`. 고친 내용은 `feedback` 표에 **오답 재료**로 남는다(평문 값 `축 고침` · `옮김` · `합침` · `합치지 않음` · `고침`, 무엇을 무엇으로 고쳤는지는 암호문). 멈춘 기록의 단계 저장값(`steps_enc`)도 같이 고쳐 이어 하기가 지운 별로 저장하지 않는다.

- `GET /suns` → `{"suns": [{"id", "name", "custom", "axis"}], "axes": ["삶의 성취", …9개, "사용자 영역"]}`. `axis` = 이어 둔 기준 축(기준 축 이름의 해는 그 자체, 아직 안 이은 해는 null).
- `POST /suns` `{"name": "통일 사역"}`(1~20자) → `{"id", "name", "custom": true, "axis", "suggested": {"axis", "basis": "낱말|임베딩|없음"}}`. 기준 축은 AI 가 제안한다: 이름이 기준 축 이름 · 대표 낱말과 겹치면 그 축(외부 호출 없음), 아니면 중심 보정 임베딩이 가장 가까운 축(Solar 임베딩 한 번, 가명 처리 · 실명 검사 뒤, `runs` 에 `suggest_axis` 로 비용), 임베딩을 못 쓰면 `사용자 영역`. 고정 문턱 없음. 동의 전이면 403 `consent_required`, 이미 사용자 해면 409 `already_exists`. 같은 이름의 해가 일기에서 이미 생겼으면 사용자 해로 표시만 한다. 새 해는 행성이 없어도 `/universe` 의 `suns` 에 뜬다.
- `PATCH /suns/{id}` `{"axis": "<axes 중 하나>"}` → 해(사용자가 AI 제안을 바꿈 → 오답 재료 `축 고침`). 기준 축 이름의 해는 409 `base_axis`.
- `PATCH /stars/{id}` `{"sun_id": "d_…"}` → `{"id", "sun_id", "name"}`. 작은 별 · 그 별의 생각 · 그 별이 주인인 기록의 해를 바꾼다(우주에서 행성이 따라감). 다음 글의 같은 주제도 옮긴 해로 간다.
- `GET /stars/merge` → `{"candidates": [{"a": {"id", "name"}, "b": {"id", "name"}, "sun", "why"}]}`: `rules.merge_candidates`(띄어쓰기만 다른 이름, 같은 해에서 서로 가장 가까운 두 별. 별 벡터 = 그 별 생각 벡터의 평균, 외부 호출 없음). '기타 생각' 별과 거절한 짝은 빼고.
- `POST /stars/merge` `{"from_id", "into_id"}` → into 별. from 의 생각이 into 의 이름 · 해로 가고, 관계 · 상태의 주제 이름도 바뀌고, from 은 지운다. 옛 이름은 비슷한 말(`settings.topic_aliases`)로 남아 다음 글에서 기록 Agent 가 옛 이름을 내도 into 로 간다.
- `POST /stars/merge/decline` `{"from_id", "into_id"}` → `{"ok": true}`(그 짝은 다시 제안하지 않음).
- `PATCH /thoughts/{id}` `{"kind"?: "<kinds>", "value"?: "<values>|null"}` → Thought. 고친 칸마다 오답 재료 `고침`(`{field, from, to}`). 종류가 다짐이 아니게 되면 금빛 고리(다짐 상태)를 거두고, 다짐 · 질문이 되면 열림으로 시작한다. 감정이 아니게 되면 '감사' 표시를 거둔다.

## 5. 되고 싶은 모습

- `GET /aspiration` → `{"current": Aspiration|null, "history": [Aspiration], "ask": {"should_ask": true, "step": 1}}`
- `POST /aspiration` `{"now": "요즘의 나", "want": "되고 싶은 나", "obstacle": "걸리는 것", "if_then": "~면 ~하겠다", "values": ["배려"]}` → Aspiration(바뀌면 새 판, 이력 보존)
- `POST /aspiration/decline` `{"mode": "skip|stop"}`(이번엔 넘어가기 / 그만 묻기) → `{"ok": true}`
- `history`는 지금 판을 뺀 지난 판(최근 것이 앞). `values`는 v8.json 가치 이름만, 3개까지. `ask.should_ask`: 판이 없고 거절하지 않았고 쓴 날이 3일 이상.
- `skip`(이번엔 넘어가기)은 계기가 생기면 풀린다: 그 뒤 글에서 바뀜이 나오거나, 이미 '실수'가 있는 주제에 어긋남이 또 나오면 `/me` 의 `onboarding.aspiration` 이 `none` 으로 돌아가고 `should_ask` 가 다시 `true`, 그 글의 `next_question.kind` 는 `aspiration`(날씨 · 다짐 안부 · 남은 질문이 먼저 잡히면 `/aspiration` 화면에서만 다시 물음). 계기가 위기 글 · 무거운 날(비 · 천둥 · 상실 · 위기 판정 실패 · 오늘은 위로만)에 생기면 그 글에선 묻지 않고 다음 글에서 묻는다. `stop`(그만 묻기)은 사용자가 `POST /aspiration` 으로 적을 때까지 그대로.
- Aspiration = `{"id", "said", "values", "obstacle", "if_then", "said_at", "reached": [{"entry_id", "quote", "at"}]}`

## 6. 나 · 설정 · 운영

- `GET /me` → `{"user": {"id", "email"}, "settings": Settings, "onboarding": {"entries": 0, "aspiration": "none|asked|skip|stop|set", "weather_asked": false}}`
- `PATCH /settings`(일부만) → Settings
  - Settings = `{"tone": "다정하게|담백하게|고양이처럼|팩폭|직접 정하기", "tone_note": "", "fact_bomb_ack": false, "gentle_today": "YYYY-MM-DD|null", "comfort_only_today": "YYYY-MM-DD|null", "suggestions": "적게|보통|많이", "cross_links": "숨김|눌렀을 때|항상", "weather_ask": true, "keeper_name": "별지기", "theme": "밤하늘", "keeper_look": "글자"}`
  - `keeper_name`: 별지기 이름(1~12자, 화면 말풍선에만 씀 · LLM 에 보내지 않음).
  - `theme`: 우주 테마 `밤하늘|새벽|오로라|먹`(기본 밤하늘 = 예전 색). 우주 화면의 바탕 · 해 · 별 · 행성 색만 바뀌고 선 · 고리처럼 뜻이 있는 색은 그대로. 목록 밖 값은 422.
  - `keeper_look`: 별지기 모습 `글자|별|달|고양이|행성`(기본 글자 = 이름 첫 글자 동그라미, 나머지는 `public/keeper/*.svg`). 화면에만 씀 · LLM 에 보내지 않음. 목록 밖 값은 422.
  - 팩폭은 `fact_bomb_ack: true`(경고 확인) 뒤에만 고를 수 있다(아니면 409 `fact_bomb_ack_required`). 경고 확인을 거두면 말투는 다정하게로.
  - `tone_note`(2026-10-28): 직접 정하기의 말투 바람. 200자 안(넘으면 422), 줄바꿈 · 탭은 띄어쓰기로, 제어 · 폭 없는 글자는 빼고 한 줄로 저장. 말투가 `직접 정하기`인데 바람이 비면 422 `tone_note_required`. 다른 말투로 바꿔도 남겨 둔다. 말 걸기 · 대화 프롬프트의 `[사용자가 원한 말투]` 절에만 들어가고(가명 처리), 고정 규칙 절(`[지킬 것]` · 상황 · 답 형식)이 늘 이긴다. 위기 글 · 무거운 날엔 쓰지 않고 다정하게(`app/service/voice.custom_note`). 바람을 쓴 말은 넘지 않는 선을 Solar 로 한 번 더 판정한다(팩폭과 같음).
- `DELETE /me` → 204. 계정과 모든 기록 지우기(되돌릴 수 없음). 순서: 벡터(Chroma) → DB 의 그 사용자 행 전부 → Supabase auth 계정(관리 API, 서버 환경변수 `SUPABASE_SERVICE_ROLE_KEY`, 남은 행은 FK cascade). 벡터를 못 지우면 아무것도 지우지 않고 503 `vector_delete_failed`(계정 그대로, 다시 시도). 정리 중인 기록이 있으면 409 `already_running`, 서비스 키가 없으면 503 `account_delete_unconfigured`, auth 삭제 실패는 502 `account_delete_failed`(다시 시도하면 이어서 지움). 화면: 설정 맨 아래 "계정과 모든 기록 지우기"(되돌릴 수 없다는 안내 + '지우기' 입력 확인) → 끝나면 로그아웃. Studio 에 올린 입력 파일은 실행이 끝날 때마다 이미 지운다.
- `GET /health` → `{"status": "ok", "version": "0.8.0"}`. `GET /health?deep=1`(2026-10-29) → DB(`select 1`) · ChromaDB(컬렉션 열기)까지 보고 `checks: {"db", "vectors"}` 를 붙인다. 하나라도 안 되면 503 · `status: "degraded"`(값은 `ok` 또는 오류 종류 이름).
- `GET /stats` → 원문 없는 운영 숫자(본인 것만): `{"entries", "entries_done", "days_written", "suns_with_entries", "feedback": {값: 수}, "yes_ratio": 맞아요/(맞아요+아니에요) 또는 null, "month_cost_usd"}`.

## 6.1 동의 (WS24, 2026-10-13)

첫 로그인 동의. 문구는 화면(`infra/frontend/app/consent` · `privacy` · `terms`)에, 판 번호는 백엔드 `app/api/consent.py` 의 `VERSION` 에 둔다. 문구를 바꾸면 `VERSION` 을 올려 모두에게 다시 묻는다.

- `GET /consent` → `{"version": "2026-10-13", "needed": true, "agreed": null | {"version", "operator_read": false, "at": "ISO"}}`. `needed` = 동의가 없거나 가장 최근 동의가 옛 판. 화면은 로그인 뒤 `needed` 면 `/consent` 로 보낸다(동의 없이 열리는 화면: `/consent` · `/privacy` · `/terms` · `/settings`).
- `POST /consent` 본문 `{"version": "<GET 의 version>", "required": true, "sensitive": true, "age14": true, "operator_read": false}` → GET 과 같은 모양.
  - `required` = 이용약관 · 개인정보 수집 · 이용 · 외부 처리(국외 이전 포함), `sensitive` = 민감정보(건강 · 신앙 등) 따로, `age14` = 만 14세 이상, `operator_read`(선택) = 품질 개선을 위해 운영자가 내가 남긴 피드백과 그 대상 문장을 읽을 수 있음.
  - 오류: 판이 다르면 409 `consent_outdated`(화면을 새로 고침), `age14` 가 거짓이면 403 `under_14`(아무것도 저장 안 함), `required` · `sensitive` 가 거짓이면 422 `consent_missing`.
  - 동의할 때마다 `consents` 표에 한 줄 덧붙인다(고치지 않음, 계정 지우기 때 같이 지움). 선택 동의를 거두려면 `operator_read: false` 로 다시 보낸다.
- 운영 화면(WS22)은 `consent.operator_read(s)` 가 참인 사용자의 피드백 원문만 풀어 보인다(다른 사람 이름은 가명, 열람 기록은 WS22).

## 6.2 운영 화면 · 선호 맞추기 제안 (WS22, 2026-10-14)

화면 `/ops`(메뉴에 없음, 검색 제외). `/ops/*` 는 백엔드 환경변수 `ADMIN_EMAILS`(쉼표 목록, 운영자 구글 계정)의 계정만 열린다. 아니면 403 `not_admin`, 비어 있으면 아무도 못 본다. 코드: `app/api/ops.py` · `app/repository/ops.py`, 마이그레이션 `20261014000200_v8_ops.sql`.

- `GET /ops/summary` → 모든 사용자의 숫자 · 코드 · id · 시각만(원문 0건). DB 는 운영 전용 역할 `app_ops` 로 읽고, 이 역할은 평문 칸에만 select 권한이 있다(암호문 `enc` · `steps_enc`, 작은 별 · 사람 · 해 이름 표는 권한 없음).
  - `cost`: `{"total_usd", "month_usd", "budget_usd": 50, "used_ratio", "warn"(80% 이상), "over"(100% 이상), "by_step"}` — 운영 `runs.est_usd` 합계(예산은 v8.json `limits.studio_budget_usd`). 개발 · 시험 원장(`runs/cost_ledger.jsonl`)은 따로.
  - `runs`: 단계별 `{step, count, avg_ms, fails, est_usd}`, 글 한 편(기록 id)당 평균 시간 · 비용, 최근 30번. `gates`: 실명 관문이 막은 요청(`real_name_leak`), 말 걸기 검사로 다시 만든 한마디(voice `meta.checks > 0`). `failures`: 실패한 기록 수 · 코드별 · 최근 30개, 단계 · 코드별 실행 오류. `eval`: 골든셋 결과 파일(`eval/results`) 요약 — 배포 번들에는 `eval/` 이 없어 `null`.
  - `satisfaction`: 점선 맞아요 비율 · 버튼별 반응 수 · 설정 번호별 반응 · 다음 날 다시 쓴 비율(`{pairs, returned, ratio}`, 사용자가 서비스를 쓴 날 = 기록을 만든 날 + 대화한 날, 다음 날이 다 지난 날만 셈). `direction.multi_sun`: 최근 14일 사용자별 글의 해 가짓수 평균 · 2개 이상 비율 · 전체 평균. `direction.closer_feeling` 은 늘 `null`('가까워졌다는 느낌'은 묻지 않음, 2026-10-13).
  - `voice`: 한마디 수, 제안 넣은 비율(`messages.suggested`), 지난 한마디와 비슷해 다시 만든 비율(`messages.repeated`), '별로' 비율, 제안 있음/없음 날의 다음 날 다시 쓴 비율. 두 칸은 이 마이그레이션 뒤 저장한 한마디부터 채워진다(전의 행은 세지 않음).
  - `talk`: 대화 수 · 평균 턴 · 정리한 대화 · 그만둔 대화(마지막 턴 뒤 24시간 동안 정리 없음) · 그만둔 턴별 수 · 제안 직후 그만둔 비율(제안 없는 턴과 비교) · 요약 확인에서 고친 비율. **대화 · 요약 확인 갈래(WS19 · WS20)가 `runs` 에 남기는 약속**(원문 없음, `diary.add_run(s, id, step, ms, calls, usd, None, meta)`):
    - `step="chat_turn"`, `entry_id`=대화 id, `meta={"turn": n, "suggested": true|false}` — 별지기가 한 턴 답할 때마다(Solar 비용도 여기)
    - `step="chat_done"`, `entry_id`=대화 id, `meta={"turns": n}` — '대화 마치고 정리하기'
    - `step="confirm"`, `entry_id`=기록 id, `meta={"items": n, "edited": k}` — 요약 확인에서 '확인하고 우주에 저장'(항목 n 개 중 고친 k 개)
  - `other_values`: 목록 밖 값('기타')이 나온 수(종류 · 확신 · 가치). `feedback_text`: '불편한 점 한 줄' 수(동의한 사용자 · 동의하지 않은 사용자). `users`: 사용자 수 · 최근 7일 쓴 사람 · 운영자 열람 동의 수.
- `GET /ops/feedback?days=30&wrong=false` → 운영자 열람에 동의한 사용자(가장 최근 동의가 지금 판이고 `operator_read` 참)만, 그 사용자 세션(`app_user` · RLS)으로 풀어 글 칸만 가명 처리: `{"days", "wrong", "users", "items": [{"user": "사용자 1", "at", "target", "value", "text"(불편한 점 한 줄의 글), "target_text"(관계: '[종류] 그때 생각 → 지금 생각 (설명)' · 한마디 · 다짐 · 기록 요약), "config"}], "other_candidates": [{"field", "original", "count"}], "not_consented": {값: 수}}`. 마음 상태 버튼(오늘은 위로만 · 살살)은 '상태 버튼'으로만(풀지 않음). 부를 때마다 사용자별 열람 기록 한 줄(`ops_reads`: 운영자 id · 사용자 id · `feedback|wrong|summarize` · 본 수). `wrong=true` 면 오답 재료('아니에요' · '별로' · '불편한 점 한 줄')만, 새 값 후보 없이.
- `POST /ops/feedback/summarize?days=30` → 피드백 정리 Agent(Solar 한 번, 누를 때만): 동의한 오답 재료(가명, 최근 200줄까지)를 이유(잘못 나눔 · 틀린 연결 · 설교 같음 · 같은 말 반복 · 화면 · 기타)별로 묶고 고칠 곳(기록 Agent · 관측 Agent · 말 걸기 규칙 · 화면)을 제안: `{"days", "users", "lines": [가명 줄], "groups": [{"reason", "items": [줄 번호], "count", "fix_where", "suggestion"}], "est_usd"}`. 보내기 전 실명 관문(`llm.guard`), 비용은 운영자 계정의 `runs`(`step="ops_summarize"`)에. 형식 · 호출 실패는 502 `summarize_failed`(열람 기록 없음).
- `GET /settings/suggestions` → `{"suggestions": [{"setting": "cross_links|suggestions", "from", "to", "reason"}]}`: 내 피드백으로 본 "이 설정으로 바꿀까요?". 영역을 넘는 관계에 '아니에요'(또는 '맞아요')를, 제안이 든 한마디에 '별로'(또는 '좋아요')를 3번 이상 · 반대쪽의 두 배 이상 누르면 한 칸 옮기기를 제안한다(바꾸는 것은 사용자, 화면: 설정 맨 위 카드).
- `POST /settings/suggestions/seen` → `{"ok": true}`: 제안을 보고 골랐음(바꿨든 그대로 뒀든). 그 뒤의 피드백만 다시 센다.
- 주 1회 오답 모으기: `scripts/collect_feedback.py`(운영 DB 를 직접 읽지 않고 `GET /ops/feedback?wrong=true` 를 부름) → `runs/wrong/YYYY-MM-DD.jsonl`(git 제외). 토큰은 운영 화면의 '스크립트용 토큰 복사'(운영자 로그인 토큰)를 `OPS_TOKEN` 으로.

## 7. WS5 구현 메모

- 코드: `main.py`(FastAPI) · `app/api`(diary.py = 일기 · SSE, routes.py = 나머지) · `app/agents`(graph.py = Super Graph, tools.py, studio.py) · `app/repository`(Postgres · Chroma · 메모리 가짜, 암호화) · `app/core`(config · security · auth · logger · seed · llm).
- 그래프: `safety → names → record(하위 그래프: record_input → record_agent → record_clean) → observer(하위 그래프: past → observe → rules) → voice → save`. 위기 글도 같은 길(시험 단계). 가치 이름 · 빈 주제는 '기타 생각' 작은 별로 모은다(그 별은 기록 Agent 의 기존 작은 별 목록에 넣지 않음). 노드마다 상태를 `entries.steps_enc`(암호화)에 남기고, 이어 하기는 끝난 노드를 건너뛴다. 끝나면 단계별 저장값은 지운다.
- 외부로 보내는 글은 호출마다 한 번에 가명 처리(`tools.mask_obj`: 한 요청 안에서는 같은 사람 = 같은 가명) → 보내기 바로 전 `assert_no_real_names`(`llm.guard`, 실명이면 보내지 않고 `real_name_leak`) → 받은 답을 그 요청의 표로 되돌림.
- 저장: 원문(본문 · 제목 · 요약 · 생각 · 인용 · 변화 · 작은 별 이름 · 사람 이름 · 관계 설명 · 상태 이력 · 한마디 · 되고 싶은 모습)은 `enc`(AES-256-GCM, 사용자별 키 HKDF(DIARY_ENC_KEY, user_id), aad `표:행 id`)에만. 위기 표시(`crisis`) · 한마디 모드(`comfort`) · 안부 한 줄 · 설정(오늘은 위로만 · 살살 날짜 포함) · 마음 상태 버튼 값도 enc 안에. 백엔드는 요청마다 백엔드 전용 역할 `app_user`(PostgREST 가 모르는 역할) + `app.user_id` 로 트랜잭션을 열어 RLS 가 백엔드 쿼리에도 걸린다. anon · authenticated 는 표 권한이 없다(supabase/migrations/20261009000000_v8_security.sql).
- 벡터: Chroma 컬렉션 `thoughts`(문서 없음, 메타 user_id · entry_id · star_id · written_at · kind). 벡터는 가명 글의 임베딩.
- 실행 기록: `logs/agent_flow_YYYYMMDD.log`(LOG_TO_FILE=1) 또는 표준 출력. 단계 · 시간 · 호출 수 · 추정 비용 · id · 오류 코드 · voice 검사 문제 개수만(상황 이름 · 위로 모드 · 위기 여부는 남기지 않음). 시각 · 파일 날짜는 KST. 같은 숫자가 `runs` 표에도(이번 달 비용 상한 · 하루 수 계산, `est_usd >= 0` check).
- 로컬: `scripts/dev_up.sh`(로컬 Supabase · ChromaDB · `.env.local` · 시험용 계정 tester@ · e2e@my-universe.test · 하늘 데모 우주) → `uv run --frozen uvicorn main:app --port 8001`. e2e 결과: `docs/ws5-e2e.md`.
- id 모양: 기록 `e_<hex>`, 생각 `<기록 id>-tNN`(글 속 순서), 관계 `<옛 생각 id>><새 생각 id>`, 사람 `p_` · 작은 별 `s_` · 해 `d_` · 되고 싶은 모습 `a_` · 이름 질문 `q_`. 화면은 모양에 기대지 말고 문자열로만 다룬다.

## 8. 대화 · 요약 확인 (WS19 · WS20, 2026-10-14)

이야기하기 화면(`/talk`). 서비스가 먼저 묻고, 사용자 말 한 턴마다 대화 그래프가 답한다. 턴 원문은 서버 `conversations.enc` 에만(사용자별 키로 암호화, 2026-10-13 동규: 다른 기기에서 이어 하기). 확인하고 저장하면 그 대화는 지우고 확인한 정리본(기록)만 남는다. 확인 전 대화는 사용자가 지우거나 계정 지우기 때 같이 지운다. 외부 AI 로 나가는 요청(턴 · 정리하기 · 확인)과 새 대화는 동의를 먼저 본다(403 `consent_required`).

Conversation = `{"id", "created_at", "updated_at", "turns": [Turn], "summary": "지금까지 정리(사용자 말만 근거)", "from_entry": "기록 id|null", "entry_id": "확인 전 초안 기록 id|null", "turn_count": 사용자 턴 수, "wrap": 마지막 답이 정리 제안이면 true}`
Turn = 별지기 `{"role": "keeper", "kind": "first|vow|question|aspiration|continue|free|reply|recall|wrap", "text", "mode": "normal|comfort", "tone", "check_in": "안부 한 줄|null", "at"}` / 사용자 `{"role": "user", "text", "via": "text|voice", "at"}`

- `POST /talk` 본문 없음 또는 `{"from_entry": "기록 id"}` → Conversation. 첫 말은 LLM 없이 정한다(PRD §6.2): `from_entry`(끝난 기록)면 그 기록을 이어 하는 말(`continue`) → 다짐 안부(`vow`, 쓰기 화면 말풍선과 같은 다짐) → 기록이 없으면 첫 만남 질문(`first`) → 지난 글의 '다음에 써 볼 질문'(`question` · `aspiration`) → 되고 싶은 모습을 물을 때(`aspiration`) → 그 밖(`free`). 사용자 말이 한 번도 없는 대화는 새로 열 때 치운다.
- `GET /talk` → `{"conversations": [Conversation]}` 최근 것부터 5개(이어 하기). `GET /talk/{id}` → Conversation. 남의 · 없는 대화는 404.
- `DELETE /talk/{id}` → 204(확인 전 초안 기록도 같이 지움, 정리 중이면 409).
- `POST /talk/{id}/turn/stream` `{"text": "1~8000자", "via": "text|voice"(기본 text, 받아쓴 말은 voice — WS21)}` → SSE: `event: progress` `{"conversation_id", "step": "safety|past|reply|summary", "label"}` … `event: turn` Conversation, 또는 `event: error` `{"conversation_id", "code": "llm_failed|real_name_leak|internal|not_found", "message", "resumable"}`. 실패한 턴은 저장하지 않는다(화면이 같은 말을 다시 보냄). 받아쓴 말(WS21)도 같은 길. `POST /talk/{id}/turn` 은 스트림 없이 Conversation(시험 · curl용, 실패는 502).
  - safety: 매 턴 위기 2단 판정(규칙 + Solar). 위기면 그 답은 위로(팩폭도 다정하게, 질문 · 제안 없음, `mode: comfort`) + `check_in`(안부 한 줄). Solar 2차 판정이 실패한 턴은 평소 답 + 안부 한 줄. 위기 표시는 대화 암호문 안에만.
  - past: 사용자 말을 가명 처리 → 질의용 임베딩 → 그 사용자의 끝난 기록의 생각 벡터에서 `rules.pick_past`(코드 코사인). `from_entry` 면 그 기록의 생각을 앞에.
  - reply: Solar. 따옴표 인용은 사용자 말 · 지난 생각 원문에 글자 그대로 있어야 하고(아니면 다시 · 기본 문장), 질문은 한 번에 하나, 넘지 않는 선 · 반복 · 사람 판정은 한마디와 같은 검사(`voice.checks.problems`). 지난 기록을 묻는 말("예전에 진로 얘기 뭐라고 했지?")은 찾은 기록의 날짜 · 원문 인용으로 답하고(`kind: recall`), 없으면 못 찾았다고 한다(찾을 기록이 없으면 Solar 를 부르지 않음). 끝낼 신호("이제 그만 잘게")나 사용자 턴 8번이면 한 줄 되짚고 정리 제안(`kind: wrap`, 마지막 줄은 고정 문장).
  - summary: 사용자 턴 3번마다(또는 300자 넘는 긴 말이면 바로) '지금까지 정리'를 사용자 말만 근거로 고쳐 쓴다(400자 안, 600자를 넘으면 문장 끝에서 자름 — WS21). 사용자 말에 없는 인용 · 사람 판정이 있으면 앞 정리를 그대로 둔다.
  - 긴 이야기(300자 넘는 말, 녹음 등 — WS21): 위기 턴이 아니면 상황 '긴 이야기'(다 되짚지 않고 들었다는 한 문장 + 마음이 실린 한 가지만 짧게 이어 묻기), 답 검사에 걸리면 세 번까지 써 본다(짧은 말은 두 번).
  - 가명 표 = 사람 목록 + 이 대화의 새 이름 후보(확실하지 않아도 가명). 대화 중에는 사람 목록에 등록하지 않는다(초안이 일기 그래프의 names 단계를 지날 때 등록). 보내기 직전 실명 검사(`llm.guard`).
  - 실행 기록(운영 지표 약속, §6.2): `runs` 에 `chat_turn`(entry_id = 대화 id, meta: 턴 번호 · 답 종류 · 검사 문제 개수 · 지난 생각 수 · 제안 여부 `suggested`) · `chat_done`(entry_id = 대화 id, meta: 사용자 턴 수 · fallback) · 요약 확인 `confirm`(entry_id = 기록 id, meta: `items` · `edited`). 이번 달 추정 비용에 같이 들어간다.
- `POST /talk/{id}/finish/stream` → SSE: `progress` `{"step": "draft", "label": "대화를 일기로 정리하는 중", "done": 0}` → 일기 그래프의 `progress`(safety … voice, save 없음) → `event: result` EntryResult(`status: "confirm"`, `confirmed: "확인 전"`, `source: "대화"`, `message` · `next_question` 은 null — 저장 뒤에 보임). 초안은 사용자 말만 근거(Solar), 사용자 말에 없는 인용 · 사람 판정 · 위기였던 대화에서 그 말이 빠지면 다시, 두 번 다 걸리면 사용자 말을 그대로 이은 글. 그 뒤로 말이 없으면 같은 초안을 다시 준다(Studio 안 부름), 말이 늘었으면 옛 초안을 지우고 다시 만든다. 사용자 말이 없으면 409 `no_turns`.
- `POST /diary/stream` 본문의 `confirm: true` 는 어느 출처든 save 앞에서 멈춘다(대화 출처는 늘 멈춤). 기본 false 면 지금과 같다.
- `POST /diary/{id}/confirm` `{"summary": "고친 요약(안 고쳤으면 빼기)", "fixes": [{"id": "생각 id", "kind": "v8 종류"}, {"id": "생각 id", "remove": true}], "agreed": ["summary", "생각 id"]}` → EntryResult(`status: "done"`, `confirmed: "확인됨"`, 한마디 포함). 원문 인용은 고치지 못한다(G1). 뺀 생각은 그 관계 · 닿은 순간 · 벡터도 뺀다. 생각 종류를 고쳤거나 생각을 뺐으면 저장할 때 한마디를 고친 생각으로 다시 만든다(Solar 한 번, 요약만 고쳤거나 맞아요뿐이면 처음 한마디 그대로 — 2026-10-14 결정). 고친 것은 `feedback`(target `confirm`, value `확인 고침`, 대상 문장 · 고치기 전후는 암호문), 맞아요는 `확인 맞아요`로 남긴다(오답 재료, 기록을 지우면 같이 지움). 저장하면 그 대화를 지운다. 확인을 기다리는 기록이 아니면 409 `not_waiting`, 모르는 생각 id · 보기 밖 종류는 422, 남의 기록은 404, 정리 중이면 409.
- 확인 전 초안은 `GET /diary` 목록 · `GET /universe` 에 보이지 않는다(`GET /diary/{id}` 는 `status: "confirm"`). 확인하지 않고 `DRAFT_KEEP_HOURS`(기본 72, 0 = 안 지움)보다 오래 둔 초안은 따로 도는 작업 없이 다음 요청(일기 쓰기 · 새 대화 · 정리하기) 때 오래된 것부터 지운다(대화는 남아 다시 정리할 수 있음).

## 9. 인스타그램 가져오기 (WS17, 2026-10-14)

화면 `/import`(쓰기 화면의 '인스타그램 글 한꺼번에 가져오기'). 순서: ① 브라우저가 '내 정보 다운로드' ZIP(JSON 형식)에서 `posts_N.json` 만 꺼낸다(사진 · 영상은 읽지 않음, ZIP64 포함, `posts_1.json` 을 바로 골라도 됨) ② 미리 보기 ③ 사용자가 '전부 / 최근 N편'을 고름(글 수 · 예상 시간 · 비용을 먼저 보임) ④ 고른 글 중 **오래된 것부터** 한 편씩 `/diary/stream` ⑤ 멈추기(지금 글까지) · 이어 하기(다음 글부터). 새로고침한 뒤에는 ZIP 을 다시 고르면 이미 가져온 글이 표시된다.

- `POST /import/instagram/preview` 본문 `{"posts": [{"title": "캡션", "creation_timestamp": 1774714800, "media": [{"title": "", "creation_timestamp": null}]}]}` — 인스타 게시물 모양에서 캡션 · 시각만(첫 사진 하나, 모르는 칸은 422). 캡션은 인스타가 적은 그대로(깨진 한글, 앞뒤 공백을 떼지 않음). 로그인만 필요(동의 확인 · 위기 판정은 `/diary/stream` 이 함).
  - 응답 `{"posts": [ImportPost], "max_posts": null | 수, "est_seconds_per_post": 60, "est_usd_per_post": 0.15}`. `posts` 는 최근 것부터.
  - ImportPost = `{"ref": "ig:<첫 게시물 시각>", "written_at": "게시 시각 ISO(+09:00)", "title", "text", "day", "day_basis": "확실|추정", "day_check", "parts": 묶은 게시물 수, "too_long": 본문이 MAX_TEXT_CHARS 를 넘음(화면이 건너뜀), "imported": 이 원본으로 정리가 끝난 기록이 이미 있음}`.
  - 정리(`app/service/importer`, 1차 importer.py 에서 옮김): 깨진 한글 복원(UTF-8 바이트가 latin-1 글자로 적힘), 사진만 있는 게시물 뺌, 하루 안에 이어 쓴 게시물('(2)…'로 시작하거나 앞 글이 '이어짐 · => · (계속)'으로 끝남)을 한 편으로(묶인 글의 짧은 표시 줄만 지움), 40자 이하 첫 줄은 제목, 글이 다루는 날은 §1 과 같은 규칙(G2) — 기록을 만들 때 서버가 다시 읽는다.
  - 상한 없음(결정 12): `IMPORT_MAX_POSTS` 가 비면(기본) 무제한. 값이 있으면 `max_posts` 로 내려 주고 화면이 고를 수 있는 편수를 그만큼으로 묶는다(서버 쪽 지킴은 `DAILY_ENTRY_LIMIT` · `MONTHLY_COST_CAP_USD`).
  - 화면은 배포 서버의 요청 · 응답 크기 한도(4.5MB) 때문에 게시물 200개 남짓씩 나눠 부른다(하루 넘게 떨어진 곳에서만 잘라 이어 쓴 게시물이 갈라지지 않게).
- 글 보내기: `POST /diary/stream` `{"title", "text", "written_at": ImportPost.written_at, "source": "지난 글 묶음", "source_ref": ImportPost.ref}`. 같은 원본이 다시 오면 §1 대로 새 기록 없이 그 기록으로 안내(`duplicate: true`, 정리가 멈춘 기록이면 `duplicate` 오류 → 화면이 이어 하기). 한 편이 `real_name_leak` · `invalid_input` 이면 그 글만 '못 한 글'로 두고 다음 글로, 연결 · 동의 · 한도 오류면 멈추고 '이어 하기'.
- 시험: `tests/test_ws17_import.py`, 입력 4종 스크립트 `scripts/test_inputs.py`(ZIP · MD · TXT · 직접 쓰기, `--base` 로 미리보기 배포에도), 화면 `infra/frontend/e2e-real/ws17.spec.ts`(가짜 Upstage). 예시 ZIP(가상 인물 도담): `infra/frontend/public/samples/instagram-virtual-dodam.zip`.

## 10. 말로 쓰기 · 읽어 주기 (WS21, 2026-10-14)

받아쓰기 · 읽어 주기는 ElevenLabs(미국, 2026-10-13 동규). 목소리 · 읽을 글은 이름을 가릴 수 없어 실명 검사(`llm.guard`) 예외이고, 개인정보처리방침 · 첫 사용 동의에 밝혀 둔다(WS24). 두 경로 모두 동의를 먼저 본다(403 `consent_required`, 그 전엔 ElevenLabs 로 안 나감). 키가 없으면 503 `voice_unconfigured`, ElevenLabs 실패는 502(`stt_failed` · `tts_failed`, runs 에 오류 코드).

- `POST /voice/transcribe` 본문 = 녹음 바이트 그대로(`Content-Type: audio/*`, 멀티파트 아님) → `{"text": "받아쓴 글", "seconds": 길이}`. 형식은 파일 앞 바이트로 본다: wav · mp3 · m4a(휴대폰 음성 메모 · 사파리 녹음) · webm(크롬 녹음) · ogg(파이어폭스 녹음), 그 밖은 415 `bad_format`. 한 번에 `VOICE_MAX_BYTES`(기본 4MB)까지 — 넘으면 끝까지 받지 않고 413 `too_large`.
  - **녹음은 저장하지 않는다**: 메모리에서 ElevenLabs Scribe(`scribe_v2`, 한국어, 소리 표시 · 화자 구분 끔)로 보내고 버린다. DB · 파일 · 로그 0, 실행 기록 `runs` 에 `stt`(meta: 길이 초 · 바이트 · 형식, 비용 = 분 × `PRICE_STT_PER_MIN`)만. 받아쓴 글도 여기서는 저장하지 않는다.
  - **4.5MB 넘는 녹음(Vercel 본문 한도)**: 서버는 조각을 모으지 않는다(무상태 — Vercel 함수는 요청마다 다른 곳에서 돌 수 있음). 화면(`components/MicButton.tsx`)이 녹음을 풀어 16kHz 모노 WAV 2분 조각(약 3.8MB)으로 나누고(2분 앞 5초 안 가장 조용한 50ms 에서 자름) 하나씩 보낸 뒤 받아쓴 글을 이어 붙인다. 브라우저가 못 푸는 형식은 4MB 아래면 그대로 보낸다. 0.5초 미만 · 20분 넘는 녹음은 화면에서 막는다(입력 검사: 받아쓴 글이 한 턴 8000자 안에 들게).
  - 받아쓴 글은 화면이 이야기하기면 대화 턴(`via: voice`)으로, 쓰기 화면이면 칸에 채워 기존 길(위기 판정 · 가명 처리 · '지금까지 정리' · 요약 확인)을 그대로 탄다.
- `POST /voice/speak` `{"text": "1~2000자"}` → `audio/mpeg`(ElevenLabs `eleven_multilingual_v2`, 목소리 `ELEVENLABS_VOICE_ID`, mp3 44.1kHz 64kbps, `Cache-Control: no-store`). 별지기 답 읽어 주기(화면에서 켜고 끔, 기본 꺼짐, 이 기기에만 기억). runs 에 `tts`(meta: 글자 수, 비용 = 글자/1000 × `PRICE_TTS_PER_1K_CHARS`).

