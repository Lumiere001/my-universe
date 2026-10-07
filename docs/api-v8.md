# 나의 우주 v8 API 약속 (WS5 백엔드 ↔ WS6 화면)

작성 2026-10-08 밤(오케스트레이터). WS5와 WS6이 동시에 개발할 수 있게 먼저 정한 모양이다. 고칠 때는 두 쪽을 함께 고친다. 실제 문서는 FastAPI가 만드는 `/docs`(OpenAPI)가 최종이다.

## 0. 공통

- 백엔드: FastAPI(`main.py`), 로컬 · Docker는 `http://localhost:8001`, 배포는 Vercel(Python 함수). 화면은 `NEXT_PUBLIC_API_BASE`로 주소를 받는다. 백엔드는 `FRONTEND_ORIGIN`만 CORS 허용.
- 로그인: Supabase Auth. 화면이 받은 access token을 모든 요청에 `Authorization: Bearer <token>`으로 보낸다(`/health` · `/ontology` 제외). 백엔드는 토큰을 Supabase(`/auth/v1/user`)로 확인해 user id를 얻는다.
  - 배포: 구글 로그인(`supabase.auth.signInWithOAuth({ provider: "google" })`). 구글 OAuth 키는 동규가 아침에 넣는다.
  - 로컬: `NEXT_PUBLIC_DEV_LOGIN=1`일 때만 시험용 계정(이메일 · 비밀번호, 로컬 Supabase에만 있음) 로그인 칸을 보인다.
- 오류: HTTP 상태 + `{"error": {"code": "영문_코드", "message": "한국어 안내"}}`.
- 시각은 ISO 8601(+09:00). id는 문자열.
- 원문(일기 글 · 인용 · 사람 이름)은 실행 기록 · 오류 메시지 · `/stats`에 절대 넣지 않는다.

## 1. 일기 쓰기 (SSE)

`POST /diary/stream` 본문 `{"text": "...", "title": "선택", "written_at": "선택, 없으면 지금", "weather": "맑음|구름 조금|흐림|비|천둥|안개|null"}`

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
- 끊기면: `GET /diary/{id}`로 상태를 보고, `status`가 `failed`이거나 멈춰 있으면 `POST /diary/{id}/resume/stream`(같은 이벤트, 끝난 단계는 건너뜀).
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

`care`(위기일 때): `{"message": "...", "resources": [{"name": "자살예방 상담전화", "contact": "109", "hours": "24시간"}, {"name": "SNS 상담 마들랜", "contact": "...", "hours": "..."}]}`. 이때 `thoughts` 등은 비어 있어도 된다.

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
               "order": 0, "ring": true, "people": ["p1"], "weather": "비"}],
  "links": [{"id": "r1", "from_planet": "e1", "to_planet": "e0", "type": "긴장", "line": "점선",
             "cross_domain": true, "needs_confirm": true, "explanation": "..."}],
  "twins": [{"id": "w1", "a_planet": "e1", "b_planet": "e3", "topic": "...", "status": "열림|해소"}],
  "blackholes": [{"id": "b1", "star_id": "s1", "label": "...", "size": 3, "planets": ["e1", "e3", "e5"]}],
  "north_star": {"text": "...", "values": ["배려"]} ,
  "people": [{"id": "p1", "name": "...", "relation": "룸메이트", "planets": ["e1"]}]
}
```

- `order`: 같은 작은 별에서 먼저 쓴 기록이 0(작은 별에 가장 가까움).
- `cross_domain: true`인 선은 화면에서 행성을 눌렀을 때만 그린다(설정 `cross_links`로 정도 조절).
- `north_star`는 되고 싶은 모습이 없으면 `null`.

## 3. 피드백 · 상태 버튼

`POST /feedback` `{"target": "relation|message|vow|question|tension|entry|app", "target_id": "r1|null", "value": "맞아요|아니에요|좋아요|별로|오늘은 위로만|지켰어요|그만둘래요|불편한 점 한 줄|오늘은 살살", "text": "불편한 점 한 줄일 때만"}` → `{"ok": true, "state": {...바뀐 상태 또는 null}}`

- 맞아요/아니에요(점선 관계) → 확인/거절, 지켰어요/그만둘래요(다짐) → 닫힘, 오늘은 살살 · 오늘은 위로만 → 오늘 하루 설정. 모든 피드백은 맞춤 신호로 저장(원문 없이).

## 4. 사람

- `GET /people` → `{"people": [{"id", "name", "nickname", "relation", "auto": true, "planets": ["e1"]}]}`
- `POST /people` `{"name", "nickname", "relation"}` · `PATCH /people/{id}` · `DELETE /people/{id}`(지우기 = 저장된 글에서 이름을 관계 말로 바꾸고 문장은 남김) → `{"ok": true, "replaced": 4}`
- `POST /people/questions/{id}` `{"answer": "같은 사람|다른 사람|사람 이름 아님|..."}` → `{"ok": true}`

## 5. 되고 싶은 모습

- `GET /aspiration` → `{"current": Aspiration|null, "history": [Aspiration], "ask": {"should_ask": true, "step": 1}}`
- `POST /aspiration` `{"now": "요즘의 나", "want": "되고 싶은 나", "obstacle": "걸리는 것", "if_then": "~면 ~하겠다", "values": ["배려"]}` → Aspiration(바뀌면 새 판, 이력 보존)
- `POST /aspiration/decline` `{"mode": "skip|stop"}`(이번엔 넘어가기 / 그만 묻기)
- Aspiration = `{"id", "said", "values", "obstacle", "if_then", "said_at", "reached": [{"entry_id", "quote", "at"}]}`

## 6. 나 · 설정 · 운영

- `GET /me` → `{"user": {"id", "email"}, "settings": Settings, "onboarding": {"entries": 0, "aspiration": "none|asked|skip|stop|set", "weather_asked": false}}`
- `PATCH /settings`(일부만) → Settings
  - Settings = `{"tone": "다정하게|담백하게|고양이처럼|팩폭", "fact_bomb_ack": false, "gentle_today": "YYYY-MM-DD|null", "comfort_only_today": "YYYY-MM-DD|null", "suggestions": "적게|보통|많이", "cross_links": "숨김|눌렀을 때|항상", "weather_ask": true}`
  - 팩폭은 `fact_bomb_ack: true`(경고 확인) 뒤에만 고를 수 있다.
- `GET /health` → `{"status": "ok", "version": "0.8.0"}`
- `GET /stats` → 원문 없는 운영 숫자(본인 것만): 글 수, 피드백 종류별 수, 맞아요 비율, 쓴 날 수, 글이 있는 해 수, 이번 달 추정 비용.
