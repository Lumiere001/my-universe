# 배포 · 운영 (WS9, v8 · 10/17 판)

작성 2026-10-08 밤. 아침에 따라 할 순서는 [MORNING.md](MORNING.md). 이 문서는 "왜 이렇게 했나"와 운영 규칙.

## 1. 추천: Vercel 프로젝트 두 개

| 프로젝트 | Root Directory | 인식 | 설정 파일 |
| --- | --- | --- | --- |
| 백엔드 `my-universe-api` | 저장소 루트 | FastAPI(Python) | 루트 `vercel.json` · `.vercelignore` |
| 화면 `my-universe` | `infra/frontend` | Next.js | 없음(자동) |

**왜 두 개인가**

- 화면 코드는 이미 백엔드를 절대 주소(`NEXT_PUBLIC_API_BASE`)로 부르고, 백엔드는 `FRONTEND_ORIGIN`만 CORS 허용한다(`docs/api-v8.md` §0). 두 프로젝트면 코드 변경이 0이다.
- 한 프로젝트로 묶는 Vercel Services는 아직 **Beta**다. 10/17부터 실제 사용자가 매일 쓰니 정식 기능만 쓴다. 2차 때 필요하면 옮긴다(`vercel.json`의 `services` + rewrites).
- 화면 · 백엔드를 따로 다시 배포 · 되돌리기할 수 있다.
- 비용: Hobby는 프로젝트 수와 상관없이 무료(한도 넘으면 멈춤, 청구 없음).

## 2. 조사 결과 (2026-10-08 확인)

| 항목 | 지금 Vercel | 우리 설정 |
| --- | --- | --- |
| 진입점 찾기 | 루트(또는 `src/` · `app/`)의 `app.py` · `index.py` · `server.py` · `main.py` · `wsgi.py` · `asgi.py` 에서 `app` 변수. 직접 지정은 `pyproject.toml`의 `[tool.vercel] entrypoint = "모듈:변수"`(예전 방식 `[project.scripts] app = ...`도 됨) | 루트에 1차 `app.py`(Streamlit 순차 스크립트)가 있어 먼저 잡힐 수 있다 → `.vercelignore`로 1차 파일을 올리지 않고, `vercel.json`의 함수 키를 `main.py`로 둔다(진입점이 다르게 잡히면 빌드가 실패해서 바로 드러남). **WS5 합친 뒤 `pyproject.toml`에 `[tool.vercel] entrypoint = "main:app"` 추가 권장**(아래 §6) |
| Python 버전 | 3.12(기본) · 3.13 · 3.14. `pyproject.toml`의 `requires-python`, `.python-version`, `Pipfile.lock`에서 고름. 없거나 지원 안 하면 3.12 | 저장소 `.python-version`은 3.11(로컬 · Docker용, 2차 가이드). Vercel은 3.11을 지원하지 않으니 `.vercelignore`로 빼서 `requires-python = ">=3.11"`로 고르게 한다(→ 3.12대). 코드는 3.11 · 3.12 둘 다에서 돌아야 한다 |
| 의존성 | `pyproject.toml`(uv.lock 있어도 없어도), `requirements.txt`, `Pipfile`. uv는 설정 없이 씀 | `requirements.txt`(1차 Streamlit용)는 `.vercelignore`로 빼서 `pyproject.toml + uv.lock`만 쓰게 한다 |
| 최대 시간 | Fluid compute 기본. Hobby: 기본 = 최대 = **300초**. 스트리밍으로 보내는 시간도 포함 | `vercel.json` `functions["main.py"].maxDuration = 300`. 일기 한 편 약 70초라 한 번에 들어간다. 300초 넘으면 504 → 화면의 "이어서 하기"(`/diary/{id}/resume/stream`)로 잇는다 |
| 스트리밍(SSE) | Python 함수는 2025-01부터 스트리밍이 기본으로 켜짐(설정 필요 없음). FastAPI `StreamingResponse`로 텍스트 · SSE를 보낼 수 있다고 안내 | WS5의 `/diary/stream`(`text/event-stream`, 약 10초마다 `: keep-alive`)이 그대로 맞는다. 응답 본문 한도 4.5MB는 진행 이벤트 수준에선 문제 없음 |
| 번들 크기 | Python 함수 최대 500MB(압축 전). Python은 트리 셰이킹이 없어 프로젝트 파일이 다 들어감 | `.vercelignore`(업로드 제외) + `excludeFiles`(번들 제외)로 data/ · runs/ · docs/ · tests/ · infra/ · 1차 파일을 뺀다. 의존성(fastapi · langgraph · openai · chromadb-client · psycopg · cryptography)은 수십 MB 수준 |
| 지역 | 기본 `iad1`(미국 동부). Hobby는 지역 하나를 고를 수 있음 | `regions: ["icn1"]`(서울). Supabase도 서울(Northeast Asia)로 만들어 DB 왕복을 짧게 |
| 로그 | 표준 출력이 Runtime Logs로. Hobby 보관 **1시간**, 요청당 256줄 · 1MB | 원문 없는 한 줄 로그만(§4). 오래 볼 숫자는 DB(`/stats`)에 |
| `.vercelignore` | 프로젝트 루트에 둔다. 모노레포에서 프로젝트 쪽에 없으면 저장소 루트 것을 씀 | 화면 프로젝트도 루트 파일을 쓸 수 있어 `infra/`는 빼지 않고 모든 줄을 `/`로 고정했다 |

화면(Next.js)은 Root Directory = `infra/frontend`이면 자동 인식된다. `vercel.json` 필요 없음.

## 3. Docker (2차 가이드 ⑥)

```bash
scripts/start_docker.sh     # docker compose up -d --build → ChromaDB 8000 · 백엔드 8001 · 화면 8002
scripts/stop_docker.sh      # docker compose down (Chroma 볼륨은 남김)
```

- `Dockerfile`(루트): python 3.11-slim + uv, `uv sync --frozen --no-dev`, `uvicorn main:app --port 8001`, `LOG_TO_FILE=1`, `./logs`를 `/srv/logs`로 마운트. 이미지에는 `main.py`와 `app/`만 넣는다.
- `infra/frontend/Dockerfile`: node 22, `next build` → `next start -p 8002`. `NEXT_PUBLIC_*`는 빌드 인자(브라우저에 박히는 공개 값만).
- `docker-compose.yml`: 백엔드는 `.env`를 읽고, 컨테이너 안에서는 `CHROMA_HOST=chroma`로 compose의 ChromaDB에 붙는다(Chroma Cloud 키는 비워 씀). Supabase는 compose 밖: 로컬 `supabase start` 스택을 쓰면 `.env.docker.local`(gitignore됨)에 `SUPABASE_URL=http://host.docker.internal:54321`처럼 컨테이너용 주소만 덮어쓴다. 클라우드면 `.env` 그대로.
- 호스트 포트는 `CHROMA_HOST_PORT` · `BACKEND_HOST_PORT` · `FRONTEND_HOST_PORT`로 바꾼다(앱 설정 `CHROMA_PORT`와 이름이 겹치지 않게 따로 둠).
- GHCR 패키징은 10/17 범위 밖(2차 마감 전 동규와).

밤 시험(2026-10-08): 다른 project 이름(`ws9test`)과 호스트 포트 18000 · 18002로 화면 이미지 빌드 → 화면 200 응답 · ChromaDB heartbeat · `chromadb-client`로 컬렉션 만들기/넣기/지우기 확인. 백엔드 이미지는 `main.py`가 아직 없어 임시 `main.py`(/health만)로 Dockerfile 동작(uv sync · uvicorn · `LOG_TO_FILE=1`)만 확인했다. 시험 컨테이너 · 볼륨 · 이미지는 지웠다.

로컬 개발(Docker 없이 코드 직접): `scripts/start.sh`(Supabase 로컬 스택 · `my-universe-chroma` 컨테이너 · 백엔드 8001 `--reload` · 화면 3000) / `scripts/stop.sh`.

## 4. 운영 규칙

### 원문 없는 로그

- 남기는 것: 시각, 기록 id, 단계(`safety` … `save`), 걸린 시간, 상태, 오류 코드(영문), 설정 번호, 추정 비용, 개수.
- 남기지 않는 것: 일기 글 · 제목 · 인용 · 요약 · 사람 이름 · 되고 싶은 모습 문장 · 토큰 · 키. 예외 메시지는 원문이 섞일 수 있으니 **예외 종류(클래스 이름)와 우리 오류 코드만** 남긴다.
- Vercel은 표준 출력(보관 1시간), Docker · 로컬은 `logs/agent_flow_YYYYMMDD.log`(`LOG_TO_FILE=1`).
- 리허설 날 Vercel Logs에서 실제로 원문이 안 보이는지 눈으로 확인한다(MORNING ⑥).

### 비용 한도

| 어디 | 누가 | 무엇 |
| --- | --- | --- |
| Upstage 콘솔 | 동규 | Billing에서 한도 · 알림 메뉴가 있으면 월 한도를 건다(공개 문서에서 확인 못 함 — 콘솔에서 확인). 없으면 리허설 다음 날 · 매주 잔액을 본다. Studio 크레딧 승인 범위 $50 |
| 앱(백엔드) | WS5 | 사용자당 하루 일기 수 상한, 이달 추정 비용 상한(넘으면 새 일기 처리 멈추고 안내). env 이름은 **WS5 합친 뒤 확인**(제안: `MAX_ENTRIES_PER_DAY`, `MONTHLY_BUDGET_USD`). 이달 추정 비용은 `/stats`에서 본다 |
| Vercel | — | Hobby는 청구 없음. 한도를 넘으면 함수가 멈춘다 |
| Supabase | — | Free 플랜은 청구 없음(500MB DB). 일주일 안 쓰면 일시 정지되니 매일 쓰면 문제 없음 |
| Chroma Cloud | 동규 | Starter $0 + 사용량, 무료 크레딧 $5. 콘솔 Billing에서 사용량 확인 |

### 오류 알림 (추천 하나): GitHub Actions 하루 한 번 `/health`

`deploy/health.yml`을 `.github/workflows/health.yml`로 두고(push 뒤), 저장소 Settings → Secrets and variables → Actions → **Variables**에 `API_URL`(백엔드 주소) · `WEB_URL`(화면 주소)을 넣으면 켜진다. 변수가 없으면 아무것도 하지 않는다. 매일 09:00(KST)에 두 주소를 부르고, 실패하면 GitHub이 **예약 실행 실패 메일**을 보낸다(일정을 마지막으로 바꾼 사람에게). 추가 계정 · 비용 없음.

- 이게 잡는 것: 배포 깨짐, 환경변수 빠짐, 서버 다운. 못 잡는 것: 일기 처리 중 Studio 오류 → 그건 화면의 오류 이벤트와 피드백("불편한 점 한 줄"), `/stats`로 본다.
- Vercel 자체 알림(Observability Alerts)은 Pro 이상이라 쓰지 않는다.

## 5. 환경변수 이름 (값은 동규가 Vercel에)

백엔드(`my-universe-api`) — **WS5 합친 뒤 실제 이름 확인**:

| 이름 | 값 |
| --- | --- |
| `UPSTAGE_API_KEY` | Upstage 콘솔 키 |
| `RECORD_AGENT_ID`, `OBSERVE_AGENT_ID` | Studio 에이전트 ID(1차와 같음) |
| `V8_RECORD_CONFIG_ID`, `V8_OBSERVE_CONFIG_ID` | `2` (1판 `RECORD_CONFIG_ID=1`은 Streamlit 데모용으로 그대로) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Supabase Project Settings → API |
| `DATABASE_URL` | Supabase Connect → **Transaction pooler**(포트 6543) 주소. 서버리스라 직접 연결 대신 풀러 |
| `DIARY_ENC_KEY` | 일기 암호화 키(32바이트 base64, MORNING ⑤의 명령으로 만듦) |
| `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE` | Chroma Cloud(이 이름은 Chroma `CloudClient`가 그대로 읽는 이름) |
| `FRONTEND_ORIGIN` | 화면 주소 `https://<화면>.vercel.app` (CORS) |
| 비용 한도 | 위 §4 (WS5 이름) |

화면(`my-universe`): `NEXT_PUBLIC_API_BASE`(백엔드 주소), `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_DEV_LOGIN=0`, `NEXT_PUBLIC_MOCK=0` (`infra/frontend/.env.example`과 같음).

로컬 · Docker는 `CHROMA_HOST` · `CHROMA_PORT`(ChromaDB 컨테이너), Chroma Cloud 키가 있으면 클라우드로 붙는 방식으로 WS5가 고른다(compose는 컨테이너 안에서 `CHROMA_API_KEY`를 비워 로컬 ChromaDB를 쓰게 함).

## 6. WS5 · 오케스트레이터에게 (이 브랜치 밖 파일)

- `pyproject.toml`: `[tool.vercel]` `entrypoint = "main:app"` 추가(진입점 확정). 공식 권장 방식.
- `.env.example`: 위 §5 이름 추가.
- DB 연결: Supabase Transaction pooler는 prepared statement를 못 쓰니 psycopg는 `prepare_threshold=None`으로 연결.
- 백엔드가 데이터 파일(예: `data/` 아래 seed)을 실행 중에 읽으면 `.vercelignore` · `vercel.json excludeFiles` · `Dockerfile`의 COPY를 같이 고친다. 지금은 `main.py`와 `app/`만 쓴다고 가정.
- 오류 로그는 예외 클래스 이름 + 오류 코드만. 오류 수를 원문 없이 DB에 남기면 Hobby 로그 보관 1시간을 넘어서도 볼 수 있다(`/stats`).

## 7. 출처 (2026-10-08 확인)

- FastAPI on Vercel: https://vercel.com/docs/frameworks/backend/fastapi
- Python runtime(진입점 · 의존성 · 스트리밍 · 번들): https://vercel.com/docs/functions/runtimes/python
- Python 버전: https://vercel.com/docs/functions/runtimes/python/python-version
- 함수 한도(300초 · 500MB · 4.5MB): https://vercel.com/docs/functions/limitations
- Python 스트리밍 기본 켜짐: https://vercel.com/changelog/python-vercel-functions-now-have-streaming-enabled-by-default
- FastAPI 배포 가이드(StreamingResponse · SSE): https://vercel.com/kb/guide/ship-a-fastapi-app-on-vercel
- Services(Beta): https://vercel.com/docs/services
- .vercelignore: https://vercel.com/docs/deployments/vercel-ignore
- vercel.json(`regions` · `functions`): https://vercel.com/docs/project-configuration/vercel-json
- Runtime Logs(Hobby 1시간): https://vercel.com/docs/logs/runtime
- Chroma 클라이언트(`CloudClient`, `CHROMA_API_KEY` · `CHROMA_TENANT` · `CHROMA_DATABASE`): https://docs.trychroma.com/docs/run-chroma/clients
- ChromaDB 이미지 태그 `chromadb/chroma:1.5.9`(= `chromadb-client` 1.5.9): https://hub.docker.com/r/chromadb/chroma
