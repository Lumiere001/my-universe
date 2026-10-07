# 나의 우주 v8 API 약속 (WS5 백엔드 ↔ WS6 화면)

작성 2026-10-08 밤(오케스트레이터). WS5와 WS6이 동시에 개발할 수 있게 먼저 정한 모양이다. 고칠 때는 두 쪽을 함께 고친다. 실제 문서는 FastAPI가 만드는 `/docs`(OpenAPI)가 최종이다.

**WS5 구현에서 바뀐 점(2026-10-08):** 아래 본문에 반영했다. 요약은 맨 끝 "§7 WS5 구현 메모".

## 0. 공통

- 백엔드: FastAPI(`main.py`), 로컬 · Docker는 `http://localhost:8001`, 배포는 Vercel(Python 함수). 화면은 `NEXT_PUBLIC_API_BASE`로 주소를 받는다. 백엔드는 `FRONTEND_ORIGIN`만 CORS 허용.
- 로그인: Supabase Auth. 화면이 받은 access token을 모든 요청에 `Authorization: Bearer <token>`으로 보낸다(`/health` · `/ontology` 제외). 백엔드는 토큰을 Supabase(`/auth/v1/user`)로 확인해 user id를 얻는다.
  - 배포: 구글 로그인(`supabase.auth.signInWithOAuth({ provider: "google" })`). 구글 OAuth 키는 동규가 아침에 넣는다.
  - 로컬: `NEXT_PUBLIC_DEV_LOGIN=1`일 때만 시험용 계정(이메일 · 비밀번호, 로컬 Supabase에만 있음) 로그인 칸을 보인다.
- 오류: HTTP 상태 + `{"error": {"code": "영문_코드", "message": "한국어 안내"}}`. 코드: `unauthorized`(401) · `invalid_input`(422, 틀린 칸 이름만 알림, 입력값은 되돌려 보내지 않음) · `not_found`(404) · `already_running`(409) · `invalid_target`(409, 버튼을 누를 수 없는 대상) · `fact_bomb_ack_required`(409) · `daily_limit`(429, 사용자별 하루 글 수 `DAILY_ENTRY_LIMIT`) · `monthly_budget`(429, 사용자별 이번 달 추정 비용 `MONTHLY_COST_CAP_USD`) · `auth_unavailable` · `db_unconfigured`(503) · `internal`(500).
- 시각은 ISO 8601(+09:00). id는 문자열.
- 원문(일기 글 · 인용 · 사람 이름)은 실행 기록 · 오류 메시지 · `/stats`에 절대 넣지 않는다.

## 1. 일기 쓰기 (SSE)

`POST /diary/stream` 본문 `{"text": "...", "title": "선택", "written_at": "선택, 없으면 지금", "weather": "맑음|구름 조금|흐림|비|천둥|안개|null"}`

입력 검사: `text` 1~8000자(`MAX_TEXT_CHARS`), `title` 120자까지(줄바꿈은 띄어쓰기로), `weather`는 v8.json 보기만, 모르는 칸은 거부(422).

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

- step 순서: `safety`(위기 확인) → `names`(사람 · 가명) → `record`(기록 Agent) → `past`(지난 생각 고르기) → `observe`(관측 Agent) → `voice`(한마디) → `save`. 위기면 `safety` 다음 바로 `result`(care).
- 끊기면: `GET /diary/{id}`로 상태를 보고, `status`가 `failed`이거나 멈춰 있으면 `POST /diary/{id}/resume/stream`(같은 이벤트, 끝난 단계는 건너뜀 — 건너뛴 단계도 progress 는 다시 보낸다). 화면이 끊겨도 서버(로컬 · Docker)는 끝까지 처리한다. 서버가 다시 켜져 멈춘 기록은 `GET /diary/{id}`가 `failed`로 알려 준다.
- `error` 이벤트의 `resumable`: 실명 검사에 걸린 경우(`real_name_leak`, 밖으로 보내지 않음)만 `false`. 그 밖의 코드: `studio_timeout` · `studio_failed` · `studio_bad_output` · `llm_failed` · `internal`.
- 한 기록을 동시에 두 번 돌리지 않는다(409 `already_running`).
- 시험 · curl용으로 같은 본문의 `POST /diary`(스트림 없이 EntryResult 한 번)도 둔다.

### EntryResult

```json
{
  "id": "e1", "status": "processing|done|failed", "step": "observe",
  "written_at": "2026-10-09T23:10:00+09:00", "title": "...", "weather": "흐림",
  "crisis": false,
  "care": null,
  "info": {"summary": "...", "addressee": "나|특정 인물|신", "addressee_person": "p1|null", "events": ["..."]},
  "thoughts": [
    {"id": "t1", "text": "...", "kind": "다짐", "grateful": false, "certainty": "단정",
     "value": "성취|null", "quote": "원문 그대로", "self_change": "스스로 쓴 변화|null",
     "topic": "작은 별 이름", "star_id": "s1", "sun_id": "d1", "people": ["p1"],
     "other": "목록 밖 원래 말|null",
     "state": {"type": "다짐|질문|긴장|바뀜", "status": "열림|지켜짐|그만둠|해소|블랙홀|후보|확정", "mistake": false} }
  ],
  "relations": [
    {"id": "r1", "from": "t1", "to": "t9", "from_entry": "e1", "to_entry": "e0",
     "type": "이어짐", "group": "판단형|영향형", "line": "실선|점선", "cross_domain": false,
     "needs_confirm": true, "explanation": "...", "quote": "원문|null"}
  ],
  "past": [{"thought_id": "t9", "entry_id": "e0", "text": "...", "written_at": "..."}],
  "reached": [{"aspiration_id": "a1", "quote": "...", "message": "..."}],
  "message": {"text": "...", "tone": "다정하게", "mode": "normal|comfort|care"},
  "next_question": {"kind": "weather|aspiration|free|none", "text": "..."},
  "people_questions": [{"id": "q1", "name": "...", "question": "...", "options": ["..."]}]
}
```

`care`(위기일 때): `{"message": "...", "resources": v8.json crisis.resources}` = `[{"name": "자살예방 상담전화", "contact": "109", "hours": "365일 24시간", "note": "무료, 문자도 가능"}, {"name": "자살예방 SNS 상담 마들랜", "full_name": "마음을 들어주는 랜선친구", "contact": "카카오톡에서 '마들랜' 검색 · 마들랜 앱 · 109 문자", "hours": "365일 24시간"}]`. 이때 `thoughts` 등은 비고, `message`는 `{"text": "", "mode": "care"}`, `step`은 `save`. 위기 글은 Studio · Solar 를 부르지 않는다.

그 밖의 칸: `thoughts[].state` 는 그 생각의 다짐 · 질문 상태, 없으면 그 생각이 새 쪽인 바뀜, 없으면 그 생각이 낀 긴장(`열림|블랙홀|해소`). `relations` 는 이 기록이 새 쪽(`to_entry`)인 관계 + 이 기록에서 시작해 뒤 기록으로 이어진 관계. `people_questions[].options`: 동명이인 · 별명은 `["같은 사람", "다른 사람", "사람 이름 아님"]`, 이름인지 낱말인지는 `["사람 이름", "사람 이름 아님"]`. `next_question.kind`: voice 의 weather → `weather`, aspiration · aspiration_invite → `aspiration`, first · commitment · open_question → `free`, 없음 → `none`.

## 2. 읽기

- `GET /diary?limit=20&before=<written_at>` → `{"entries": [{"id", "written_at", "title", "summary", "weather", "status", "sun", "star"}]}`
- `GET /diary/{id}` → EntryResult
- `DELETE /diary/{id}` → 204 (생각 · 관계 · 벡터까지)
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
             "cross_domain": true, "needs_confirm": true, "explanation": "..."}],
  "twins": [{"id": "w1", "a_planet": "e1", "b_planet": "e3", "topic": "...", "status": "열림|해소"}],
  "blackholes": [{"id": "b1", "star_id": "s1", "label": "...", "size": 3, "planets": ["e1", "e3", "e5"]}],
  "north_star": {"text": "...", "values": ["배려"], "reached_planets": ["e3"]} ,
  "people": [{"id": "p1", "name": "...", "relation": "룸메이트", "planets": ["e1"]}]
}
```

- `order`: 같은 작은 별에서 먼저 쓴 기록이 0(작은 별에 가장 가까움).
- `cross_domain: true`인 선은 화면에서 행성을 눌렀을 때만 그린다(설정 `cross_links`로 정도 조절).
- `north_star`는 되고 싶은 모습이 없으면 `null`. `reached_planets`: 지금 판에 닿은 순간이 있는 행성.
- `thought_count`: 생각 수(행성 크기), `certainty`: 가장 많은 확신(같으면 단정, 밝기), `has_question`: 열린 질문이 있음('?'), `ring`: 다짐이 있음, `ring_state`: `열림`(빈 고리) · `채워짐`(지킨 다짐).
- 생각이 없는 글(위기 글 · 생각 없이 일정만 적은 글)은 행성으로 띄우지 않고 `/diary` 목록에만 있다. 같은 기록 안의 관계는 `links`에 넣지 않는다.
- `twins` id = 긴장 묶음 키(`긴장:<관계 id>`), `blackholes` 는 풀리지 않은 채 다른 날 다시 나온 긴장.

## 3. 피드백 · 상태 버튼

`POST /feedback` `{"target": "relation|message|vow|question|tension|entry|app|weather", "target_id": "r1|null", "value": "맞아요|아니에요|좋아요|별로|오늘은 위로만|지켰어요|그만둘래요|불편한 점 한 줄|오늘은 살살|날씨 건너뜀", "text": "불편한 점 한 줄일 때만(500자)"}` → `{"ok": true, "state": {"type", "status", "mistake"} 또는 null}`

- 맞아요/아니에요(`target_id` = 관계 id `옛생각id>새생각id`) → 점선을 실선으로 확인(바뀜 후보면 확정) / 관계 지우기, 지켰어요/그만둘래요(`target_id` = 다짐 생각 id) → 닫힘, 오늘은 살살 · 오늘은 위로만 → 오늘 하루 설정(`gentle_today` · `comfort_only_today` = 오늘 날짜), 날씨 건너뜀 → `weather_ask: false`(다음엔 날씨를 묻지 않음). 맞지 않는 대상(이미 닫힌 다짐 등)이면 409 `invalid_target`. 모든 피드백은 맞춤 신호로 저장(불편한 점 한 줄의 글만 암호화).

## 4. 사람

- `GET /people` → `{"people": [{"id", "name", "nickname", "relation", "auto": true, "planets": ["e1"]}]}`
- `POST /people` `{"name", "nickname", "relation"}` · `PATCH /people/{id}` · `DELETE /people/{id}`(지우기 = 저장된 글에서 이름을 관계 말로 바꾸고 문장은 남김) → `{"ok": true, "replaced": 4}`
- `POST /people/questions/{id}` `{"answer": "같은 사람|다른 사람|사람 이름|사람 이름 아님"}` → `{"ok": true}`. 다른 사람 · 사람 이름 → 사람 목록에 더함, 같은 사람(별명) → 겹치는 사람의 별명으로 더함.
- `nickname`은 쉼표로 여러 개. 새 이름은 글을 쓸 때 자동 등록(`auto: true`)된다(가명으로 보내기 위해). 손으로 고치면 `auto: false`.

## 5. 되고 싶은 모습

- `GET /aspiration` → `{"current": Aspiration|null, "history": [Aspiration], "ask": {"should_ask": true, "step": 1}}`
- `POST /aspiration` `{"now": "요즘의 나", "want": "되고 싶은 나", "obstacle": "걸리는 것", "if_then": "~면 ~하겠다", "values": ["배려"]}` → Aspiration(바뀌면 새 판, 이력 보존)
- `POST /aspiration/decline` `{"mode": "skip|stop"}`(이번엔 넘어가기 / 그만 묻기) → `{"ok": true}`
- `history`는 지금 판을 뺀 지난 판(최근 것이 앞). `values`는 v8.json 가치 이름만, 3개까지. `ask.should_ask`: 판이 없고 거절하지 않았고 쓴 날이 3일 이상.
- Aspiration = `{"id", "said", "values", "obstacle", "if_then", "said_at", "reached": [{"entry_id", "quote", "at"}]}`

## 6. 나 · 설정 · 운영

- `GET /me` → `{"user": {"id", "email"}, "settings": Settings, "onboarding": {"entries": 0, "aspiration": "none|asked|skip|stop|set", "weather_asked": false}}`
- `PATCH /settings`(일부만) → Settings
  - Settings = `{"tone": "다정하게|담백하게|고양이처럼|팩폭", "fact_bomb_ack": false, "gentle_today": "YYYY-MM-DD|null", "comfort_only_today": "YYYY-MM-DD|null", "suggestions": "적게|보통|많이", "cross_links": "숨김|눌렀을 때|항상", "weather_ask": true}`
  - 팩폭은 `fact_bomb_ack: true`(경고 확인) 뒤에만 고를 수 있다(아니면 409 `fact_bomb_ack_required`). 경고 확인을 거두면 말투는 다정하게로.
- `GET /health` → `{"status": "ok", "version": "0.8.0"}`
- `GET /stats` → 원문 없는 운영 숫자(본인 것만): `{"entries", "entries_done", "days_written", "suns_with_entries", "feedback": {값: 수}, "yes_ratio": 맞아요/(맞아요+아니에요) 또는 null, "month_cost_usd"}`.

## 7. WS5 구현 메모

- 코드: `main.py`(FastAPI) · `app/api`(diary.py = 일기 · SSE, routes.py = 나머지) · `app/agents`(graph.py = Super Graph, tools.py, studio.py) · `app/repository`(Postgres · Chroma · 메모리 가짜, 암호화) · `app/core`(config · security · auth · logger · seed · llm).
- 그래프: `safety → names → record(하위 그래프: record_input → record_agent → record_clean) → observer(하위 그래프: past → observe → rules) → voice → save`. 위기면 `safety → save`. 노드마다 상태를 `entries.steps_enc`(암호화)에 남기고, 이어 하기는 끝난 노드를 건너뛴다. 끝나면 단계별 저장값은 지운다.
- 외부로 보내는 글은 호출마다 한 번에 가명 처리(`tools.mask_obj`: 한 요청 안에서는 같은 사람 = 같은 가명) → 보내기 바로 전 `assert_no_real_names`(`llm.guard`, 실명이면 보내지 않고 `real_name_leak`) → 받은 답을 그 요청의 표로 되돌림.
- 저장: 원문(본문 · 제목 · 요약 · 생각 · 인용 · 변화 · 작은 별 이름 · 사람 이름 · 관계 설명 · 상태 이력 · 한마디 · 되고 싶은 모습)은 `enc`(AES-256-GCM, 사용자별 키 HKDF(DIARY_ENC_KEY, user_id), aad `표:행 id`)에만. 백엔드는 요청마다 `authenticated` 역할 + 그 사용자의 JWT claim 으로 트랜잭션을 열어 RLS 가 백엔드 쿼리에도 걸린다.
- 벡터: Chroma 컬렉션 `thoughts`(문서 없음, 메타 user_id · entry_id · star_id · written_at · kind). 벡터는 가명 글의 임베딩.
- 실행 기록: `logs/agent_flow_YYYYMMDD.log`(LOG_TO_FILE=1) 또는 표준 출력. 단계 · 시간 · 호출 수 · 추정 비용 · id · 오류 코드 · voice checks/situations 이름만. 같은 숫자가 `runs` 표에도(이번 달 비용 상한 계산).
- 로컬: `scripts/dev_up.sh`(로컬 Supabase · ChromaDB · `.env.local` · 시험용 계정 tester@ · e2e@my-universe.test · 하늘 데모 우주) → `uv run --frozen uvicorn main:app --port 8001`. e2e 결과: `docs/ws5-e2e.md`.

