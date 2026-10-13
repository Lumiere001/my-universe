# 나의 우주 v8 API 약속 (WS5 백엔드 ↔ WS6 화면)

작성 2026-10-08 밤(오케스트레이터). WS5와 WS6이 동시에 개발할 수 있게 먼저 정한 모양이다. 고칠 때는 두 쪽을 함께 고친다. 실제 문서는 FastAPI가 만드는 `/docs`(OpenAPI)가 최종이다(로컬에서 `API_DOCS=1`일 때만 열림, 배포는 꺼 둠).

**WS5 구현에서 바뀐 점(2026-10-08):** 아래 본문에 반영했다. 요약은 맨 끝 "§7 WS5 구현 메모".

**시험 단계 위기 대응(2026-10-08 아침, 동규 결정):** 위기 글도 7단계를 다 돌고 평소 EntryResult 를 준다. `care` 칸을 없애고 `message.check_in`(안부 한 줄)을 더했다(§1).

**기록 칸(WS11, 2026-10-13):** 쓰기 본문에 `source` · `source_ref` · `day`, EntryResult · 목록에 `source` · `day` · `day_basis` · `day_check` · `confirmed` · `record_type`, 생각에 `original`, `info.original` 을 더했다(칸 추가만). 같은 글(같은 Studio 설정) · 같은 원본이 다시 오면 Studio 를 부르지 않고 그 기록으로 안내한다(§1). 마이그레이션 `20261013000000_v8_record_fields.sql`(덧붙이기만).

**쓰기 화면 작은 묶음(WS13, 2026-10-14):** `GET /diary/prompt`(쓰기 화면 위 별지기 말풍선) · `PATCH /diary/{id}/day`(글이 다루는 날 고치기) 를 더하고(§2), Settings 에 `keeper_name`(별지기 이름)을 더했다(§6). 새 경로 · 칸 추가만이고 마이그레이션은 없다.

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
  "people_questions": [{"id": "q1", "name": "...", "question": "...", "options": ["..."]}]
}
```

기록 칸: `source` 출처, `day` 글이 다루는 날(이 칸 전에 저장된 기록은 쓴 날 · 추정), `day_check` 날짜 확인 필요(G2), `confirmed` 대화에서 온 글의 요약 확인 상태(그 밖은 null), `record_type` 기록 Agent Classify 가 고른 글 유형(목록 밖이면 `기타` + `info.original.record_type`, 이 칸 전 기록은 null). `thoughts[].original` 은 목록 밖 값의 원래 말(종류 · 확신 · 가치, 없으면 null). `other` 는 예전 화면용으로 종류의 원래 말만.

`crisis`: 위기로 감지된 글이면 true(감지 결과는 기록 enc 안에 남겨 얼마나 자주 걸리는지 본다). 시험 단계(2026-10-08 아침 동규 결정)에는 위기여도 결과 모양이 같다 — `care` 칸은 없앴고(돌봄 화면 · 109 · 마들랜 · 119 · 112 안내 없음), 생각 · 관계 · 우주 행성이 평소처럼 나온다(Studio · Solar 도 평소처럼, 가명 글로). 위기 글의 `message`는 `mode: "comfort"`(제안 · 다음 질문 없음, 팩폭이면 그 글만 `tone: "다정하게"`)이고, `message.check_in`에 안부 한 줄(코드에 둔 고정 문장, 지난 안부와 겹치지 않게)이 온다. 화면은 한마디 아래 작은 줄로 보인다. 위기 2차 판정(Solar)이 실패한 글은 평소 `message` + 같은 `check_in`. 그 밖의 글은 `check_in: null`. 정식 운영 때의 안내(v8.json `crisis.resources`)는 그때 다시 정한다.

그 밖의 칸: `thoughts[].state` 는 그 생각의 다짐 · 질문 상태, 없으면 그 생각이 새 쪽인 바뀜, 없으면 그 생각이 낀 긴장(`열림|블랙홀|해소`). `relations` 는 이 기록이 새 쪽(`to_entry`)인 관계 + 이 기록에서 시작해 뒤 기록으로 이어진 관계. `people_questions[].options`: 동명이인 · 별명은 `["같은 사람", "다른 사람", "사람 이름 아님"]`, 이름인지 낱말인지는 `["사람 이름", "사람 이름 아님"]`. `next_question.kind`: voice 의 weather → `weather`, aspiration · aspiration_invite → `aspiration`, first · commitment · open_question · widen(좁아짐 막기: 오래 비어 있는 해 · 글이 없는 기준 축을 가끔 묻기) → `free`, 없음 → `none`.

## 2. 읽기

- `GET /diary?limit=20&before=<written_at>` → `{"entries": [{"id", "written_at", "title", "summary", "weather", "status", "sun", "star", "source", "day", "day_basis", "day_check", "confirmed", "record_type"}]}`
- `GET /diary/{id}` → EntryResult
- `DELETE /diary/{id}` → 204 (생각 · 관계 · 한마디 · 그 기록 · 생각 · 관계를 가리킨 피드백 · 벡터까지. 남은 기록이 모두 끝난 상태면 이 기록에만 쓰인 작은 별 · 자동 등록 사람도 정리). 정리 중이면 409.
- `GET /diary/prompt` → `{"kind": "first|weather|aspiration|free|none", "text": "질문", "vow": {"thought_id", "text", "overdue": false} | null}` 쓰기 화면 위 별지기 말풍선(LLM 없음). 기록이 없으면 정해 둔 첫 만남 질문(`first`, PRD §6.2), 있으면 마지막 글의 '다음에 써 볼 질문'(`next_question` 과 같은 종류 · 글). 날씨 질문은 건너뛰었으면(`weather_ask: false`) `none`, 되고 싶은 모습 질문은 넘어감 · 그만 묻기 · 이미 적었으면 `none`. `vow` 는 다짐 안부: 기한이 지났거나(`overdue: true`) 마지막 글에서 나온 열린 다짐 하나(화면은 지켰어요 · 그만둘래요 버튼, 누르면 닫혀 다시 안 나옴). 마지막 글이 위로 모드(무거운 날 · 위기)였거나 오늘은 위로만이면, 또는 지난 질문이 이미 다짐 안부면 `null`. `/diary/{id}` 보다 먼저 등록한다.
- `PATCH /diary/{id}/day` `{"day": "YYYY-MM-DD"}` → EntryResult. 글이 다루는 날을 고친다(`day_basis: "확실"`, `day_check: false`). 정리 결과(생각 · 관계)는 다시 돌리지 않는다. 정리 중이면 409 `already_running`, 남의 · 없는 기록은 404.
- `GET /universe` → 아래 Universe
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

`POST /feedback` `{"target": "relation|message|vow|question|tension|entry|app|weather", "target_id": "r1|null", "value": "맞아요|아니에요|좋아요|별로|오늘은 위로만|지켰어요|그만둘래요|불편한 점 한 줄|오늘은 살살|날씨 건너뜀", "text": "불편한 점 한 줄일 때만(500자)"}` → `{"ok": true, "state": {"type", "status", "mistake"} 또는 null}`

- 맞아요/아니에요(`target_id` = 관계 id `옛생각id>새생각id`) → 점선을 실선으로 확인(바뀜 후보면 확정) / 관계 지우기, 지켰어요/그만둘래요(`target_id` = 다짐 생각 id) → 닫힘, 오늘은 살살 · 오늘은 위로만 → 오늘 하루 설정(`gentle_today` · `comfort_only_today` = 오늘 날짜), 날씨 건너뜀 → `weather_ask: false`(다음엔 날씨를 묻지 않음). 맞지 않는 대상(이미 닫힌 다짐 등)이면 409 `invalid_target`. 모든 피드백은 맞춤 신호로 저장(불편한 점 한 줄의 글만 암호화). 실행 기록(runs)에는 그때의 Studio 설정 번호 `studio_config`('기록 판/관측 판', 예 `2/2`)를, 피드백에는 누른 때가 아니라 그 대상(기록 · 생각 · 관계)의 기록을 처리한 마지막 실행의 설정 번호를 남긴다(기록과 상관없는 피드백은 null). '아니에요'로 지운 관계는 종류 · 두 생각 id 를 그 피드백의 암호문에 남긴다(오답 재료, 기록을 지우면 같이 지움).

## 4. 사람

- `GET /people` → `{"people": [{"id", "name", "nickname", "relation", "auto": true, "planets": ["e1"]}]}`
- `POST /people` `{"name", "nickname", "relation"}` · `PATCH /people/{id}` · `DELETE /people/{id}`(지우기 = 저장된 글에서 이름을 관계 말로 바꾸고 문장은 남김) → `{"ok": true, "replaced": 4}`
- `POST /people/questions/{id}` `{"answer": "같은 사람|다른 사람|사람 이름|사람 이름 아님"}` → `{"ok": true}`. 다른 사람 · 사람 이름 → 사람 목록에 더함, 같은 사람(별명) → 겹치는 사람의 별명으로 더함.
- `GET /people/{id}/thoughts` → `{"person": {"id", "name", "relation"}, "thoughts": [Thought + {"entry_id", "written_at", "title"}]}`: 그 사람과 얽힌 생각(끝난 기록만), 먼저 쓴 기록부터 · 같은 기록 안은 글 순서. 우주에서 사람을 고르면 나오는 목록. 없는(남의) 사람이면 404.
- `nickname`은 쉼표로 여러 개. 새 이름은 글을 쓸 때 자동 등록(`auto: true`)된다(가명으로 보내기 위해). 손으로 고치면 `auto: false`.

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
  - Settings = `{"tone": "다정하게|담백하게|고양이처럼|팩폭", "fact_bomb_ack": false, "gentle_today": "YYYY-MM-DD|null", "comfort_only_today": "YYYY-MM-DD|null", "suggestions": "적게|보통|많이", "cross_links": "숨김|눌렀을 때|항상", "weather_ask": true, "keeper_name": "별지기"}`
  - `keeper_name`: 별지기 이름(1~12자, 화면 말풍선에만 씀 · LLM 에 보내지 않음).
  - 팩폭은 `fact_bomb_ack: true`(경고 확인) 뒤에만 고를 수 있다(아니면 409 `fact_bomb_ack_required`). 경고 확인을 거두면 말투는 다정하게로.
- `DELETE /me` → 204. 계정과 모든 기록 지우기(되돌릴 수 없음). 순서: 벡터(Chroma) → DB 의 그 사용자 행 전부 → Supabase auth 계정(관리 API, 서버 환경변수 `SUPABASE_SERVICE_ROLE_KEY`, 남은 행은 FK cascade). 벡터를 못 지우면 아무것도 지우지 않고 503 `vector_delete_failed`(계정 그대로, 다시 시도). 정리 중인 기록이 있으면 409 `already_running`, 서비스 키가 없으면 503 `account_delete_unconfigured`, auth 삭제 실패는 502 `account_delete_failed`(다시 시도하면 이어서 지움). 화면: 설정 맨 아래 "계정과 모든 기록 지우기"(되돌릴 수 없다는 안내 + '지우기' 입력 확인) → 끝나면 로그아웃. Studio 에 올린 입력 파일은 실행이 끝날 때마다 이미 지운다.
- `GET /health` → `{"status": "ok", "version": "0.8.0"}`
- `GET /stats` → 원문 없는 운영 숫자(본인 것만): `{"entries", "entries_done", "days_written", "suns_with_entries", "feedback": {값: 수}, "yes_ratio": 맞아요/(맞아요+아니에요) 또는 null, "month_cost_usd"}`.

## 6.1 동의 (WS24, 2026-10-13)

첫 로그인 동의. 문구는 화면(`infra/frontend/app/consent` · `privacy` · `terms`)에, 판 번호는 백엔드 `app/api/consent.py` 의 `VERSION` 에 둔다. 문구를 바꾸면 `VERSION` 을 올려 모두에게 다시 묻는다.

- `GET /consent` → `{"version": "2026-10-13", "needed": true, "agreed": null | {"version", "operator_read": false, "at": "ISO"}}`. `needed` = 동의가 없거나 가장 최근 동의가 옛 판. 화면은 로그인 뒤 `needed` 면 `/consent` 로 보낸다(동의 없이 열리는 화면: `/consent` · `/privacy` · `/terms` · `/settings`).
- `POST /consent` 본문 `{"version": "<GET 의 version>", "required": true, "sensitive": true, "age14": true, "operator_read": false}` → GET 과 같은 모양.
  - `required` = 이용약관 · 개인정보 수집 · 이용 · 외부 처리(국외 이전 포함), `sensitive` = 민감정보(건강 · 신앙 등) 따로, `age14` = 만 14세 이상, `operator_read`(선택) = 품질 개선을 위해 운영자가 내가 남긴 피드백과 그 대상 문장을 읽을 수 있음.
  - 오류: 판이 다르면 409 `consent_outdated`(화면을 새로 고침), `age14` 가 거짓이면 403 `under_14`(아무것도 저장 안 함), `required` · `sensitive` 가 거짓이면 422 `consent_missing`.
  - 동의할 때마다 `consents` 표에 한 줄 덧붙인다(고치지 않음, 계정 지우기 때 같이 지움). 선택 동의를 거두려면 `operator_read: false` 로 다시 보낸다.
- 운영 화면(WS22)은 `consent.operator_read(s)` 가 참인 사용자의 피드백 원문만 풀어 보인다(다른 사람 이름은 가명, 열람 기록은 WS22).

## 7. WS5 구현 메모

- 코드: `main.py`(FastAPI) · `app/api`(diary.py = 일기 · SSE, routes.py = 나머지) · `app/agents`(graph.py = Super Graph, tools.py, studio.py) · `app/repository`(Postgres · Chroma · 메모리 가짜, 암호화) · `app/core`(config · security · auth · logger · seed · llm).
- 그래프: `safety → names → record(하위 그래프: record_input → record_agent → record_clean) → observer(하위 그래프: past → observe → rules) → voice → save`. 위기 글도 같은 길(시험 단계). 가치 이름 · 빈 주제는 '기타 생각' 작은 별로 모은다(그 별은 기록 Agent 의 기존 작은 별 목록에 넣지 않음). 노드마다 상태를 `entries.steps_enc`(암호화)에 남기고, 이어 하기는 끝난 노드를 건너뛴다. 끝나면 단계별 저장값은 지운다.
- 외부로 보내는 글은 호출마다 한 번에 가명 처리(`tools.mask_obj`: 한 요청 안에서는 같은 사람 = 같은 가명) → 보내기 바로 전 `assert_no_real_names`(`llm.guard`, 실명이면 보내지 않고 `real_name_leak`) → 받은 답을 그 요청의 표로 되돌림.
- 저장: 원문(본문 · 제목 · 요약 · 생각 · 인용 · 변화 · 작은 별 이름 · 사람 이름 · 관계 설명 · 상태 이력 · 한마디 · 되고 싶은 모습)은 `enc`(AES-256-GCM, 사용자별 키 HKDF(DIARY_ENC_KEY, user_id), aad `표:행 id`)에만. 위기 표시(`crisis`) · 한마디 모드(`comfort`) · 안부 한 줄 · 설정(오늘은 위로만 · 살살 날짜 포함) · 마음 상태 버튼 값도 enc 안에. 백엔드는 요청마다 백엔드 전용 역할 `app_user`(PostgREST 가 모르는 역할) + `app.user_id` 로 트랜잭션을 열어 RLS 가 백엔드 쿼리에도 걸린다. anon · authenticated 는 표 권한이 없다(supabase/migrations/20261009000000_v8_security.sql).
- 벡터: Chroma 컬렉션 `thoughts`(문서 없음, 메타 user_id · entry_id · star_id · written_at · kind). 벡터는 가명 글의 임베딩.
- 실행 기록: `logs/agent_flow_YYYYMMDD.log`(LOG_TO_FILE=1) 또는 표준 출력. 단계 · 시간 · 호출 수 · 추정 비용 · id · 오류 코드 · voice 검사 문제 개수만(상황 이름 · 위로 모드 · 위기 여부는 남기지 않음). 시각 · 파일 날짜는 KST. 같은 숫자가 `runs` 표에도(이번 달 비용 상한 · 하루 수 계산, `est_usd >= 0` check).
- 로컬: `scripts/dev_up.sh`(로컬 Supabase · ChromaDB · `.env.local` · 시험용 계정 tester@ · e2e@my-universe.test · 하늘 데모 우주) → `uv run --frozen uvicorn main:app --port 8001`. e2e 결과: `docs/ws5-e2e.md`.
- id 모양: 기록 `e_<hex>`, 생각 `<기록 id>-tNN`(글 속 순서), 관계 `<옛 생각 id>><새 생각 id>`, 사람 `p_` · 작은 별 `s_` · 해 `d_` · 되고 싶은 모습 `a_` · 이름 질문 `q_`. 화면은 모양에 기대지 말고 문자열로만 다룬다.
