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
| 진입점 찾기 | 루트(또는 `src/` · `app/`)의 `app.py` · `index.py` · `server.py` · `main.py` · `wsgi.py` · `asgi.py` 에서 `app` 변수. 직접 지정은 `pyproject.toml`의 `[tool.vercel] entrypoint = "모듈:변수"`(예전 방식 `[project.scripts] app = ...`도 됨) | 루트에 1차 `app.py`(Streamlit 순차 스크립트)가 있어 먼저 잡힐 수 있다 → `.vercelignore`로 1차 파일을 올리지 않고, `vercel.json`의 함수 키를 `main.py`로 둔다(진입점이 다르게 잡히면 빌드가 실패해서 바로 드러남). `tool.vercel.entrypoint`는 공식 FastAPI 문서에 있는 설정(2026-10-08 다시 확인, §7 첫 줄). `pyproject.toml`에 두 줄을 넣었다(2026-10-08 아침, MORNING ①) |
| Python 버전 | 3.12(기본) · 3.13 · 3.14. `pyproject.toml`의 `requires-python`, `.python-version`, `Pipfile.lock`에서 고름. 없거나 지원 안 하면 3.12 | 저장소 `.python-version`은 3.11(로컬 · Docker용, 2차 가이드). Vercel은 3.11을 지원하지 않으니 `.vercelignore`로 빼서 `requires-python = ">=3.11"`로 고르게 한다(→ 3.12대). 코드는 3.11 · 3.12 둘 다에서 돌아야 한다 |
| 의존성 | `pyproject.toml`(uv.lock 있어도 없어도), `requirements.txt`, `Pipfile`. uv는 설정 없이 씀 | `requirements.txt`(1차 Streamlit용)는 `.vercelignore`로 빼서 `pyproject.toml + uv.lock`만 쓰게 한다 |
| 최대 시간 | Fluid compute 기본. Hobby: 기본 = 최대 = **300초**. 스트리밍으로 보내는 시간도 포함 | `vercel.json` `functions["main.py"].maxDuration = 300`. 일기 한 편 약 70초라 한 번에 들어간다. 300초 넘으면 504 → 화면의 "이어서 하기"(`/diary/{id}/resume/stream`)로 잇는다 |
| 스트리밍(SSE) | Python 함수는 2025-01부터 스트리밍이 기본으로 켜짐(설정 필요 없음). FastAPI `StreamingResponse`로 텍스트 · SSE를 보낼 수 있다고 안내 | WS5의 `/diary/stream`(`text/event-stream`, 약 10초마다 `: keep-alive`)이 그대로 맞는다. 응답 본문 한도 4.5MB는 진행 이벤트 수준에선 문제 없음 |
| 번들 크기 | Python 함수 최대 500MB(압축 전). Python은 트리 셰이킹이 없어 프로젝트 파일이 다 들어감 | `.vercelignore`(업로드 제외) + `excludeFiles`(번들 제외)로 data/ · runs/ · docs/ · tests/ · infra/ · 1차 파일을 뺀다. 단 `data/ops/domain_aliases_*.json` · `topic_center_*.json`(해 분류용 기준 축 벡터, 약 650KB)은 백엔드가 실행 중에 읽어서 `.vercelignore`에서 `!`로 다시 넣는다(공식 문서의 allowlist 방식과 같은 `!` 문법). 의존성(fastapi · langgraph · openai · chromadb-client · psycopg · cryptography)은 수십 MB 수준 |
| 지역 | 기본 `iad1`(미국 동부). Hobby는 지역 하나를 고를 수 있음 | `regions: ["icn1"]`(서울). Supabase도 서울(Northeast Asia)로 만들어 DB 왕복을 짧게 |
| 로그 | 표준 출력이 Runtime Logs로. Hobby 보관 **1시간**, 요청당 256줄 · 1MB | 원문 없는 한 줄 로그만(§4). 오래 볼 숫자는 DB(`/stats`)에 |
| `.vercelignore` | 프로젝트 루트에 둔다. 모노레포에서 프로젝트 쪽에 없으면 저장소 루트 것을 씀 | 화면 프로젝트도 루트 파일을 쓸 수 있어 `infra/`는 빼지 않고 모든 줄을 `/`로 고정했다 |

화면(Next.js)은 Root Directory = `infra/frontend`이면 자동 인식된다. `vercel.json` 필요 없음.

## 3. Docker (2차 가이드 ⑥)

```bash
scripts/dev_up.sh           # 로컬 Supabase · 시험용 계정 · 하늘 데모 우주(.env.local)를 먼저 준비
scripts/start_docker.sh     # docker compose up -d --build → ChromaDB 8000 · 백엔드 8001 · 화면 8002
scripts/stop_docker.sh      # docker compose down (Chroma 볼륨은 남김)
# 다른 이름 · 포트로 따로 띄워 보기(지금 띄운 것과 안 겹치게):
COMPOSE_PROJECT_NAME=v8check CHROMA_HOST_PORT=18000 BACKEND_HOST_PORT=18001 FRONTEND_HOST_PORT=18002 scripts/start_docker.sh
docker compose -p v8check down -v --rmi local
```

- `start_docker.sh`는 `.env.local`이 있고 `.env.docker.local`이 없으면 `.env.local`의 `SUPABASE_URL` · `SUPABASE_ANON_KEY` · `DATABASE_URL` · `DIARY_ENC_KEY`를 주소만 `host.docker.internal`로 바꿔 `.env.docker.local`에 쓰고, 화면 빌드 인자(`NEXT_PUBLIC_*`)는 `infra/frontend/.env.local`에서 읽는다. 기본 포트 8000을 쓰면 로컬 개발용 `my-universe-chroma`를 먼저 끈다(데이터는 남음). 로컬 백엔드(8001)가 켜져 있으면 `scripts/stop.sh` 대신 그 프로세스만 끄거나 포트를 바꾼다(`stop.sh`는 Supabase까지 끈다).
- compose의 ChromaDB는 새 볼륨이라 하늘 데모의 생각 벡터가 없다. 우주 · 목록 화면은 DB만 쓰니 그대로 보이고, 새 일기의 "지난 생각 고르기"만 Docker 안에서 쓴 글부터 쌓인다.
- `Dockerfile`(루트): python 3.11-slim + uv, `uv sync --frozen --no-dev`, `uvicorn main:app --port 8001`, `LOG_TO_FILE=1`, `TZ=Asia/Seoul`(로그 파일 이름 · 시각을 로컬과 같게), `./logs`를 `/srv/logs`로 마운트. 이미지에는 `main.py` · `app/` · `data/ops`의 기준 축 벡터 파일 2개만 넣는다.
- `infra/frontend/Dockerfile`: node 22, `next build` → `next start -p 8002`. `NEXT_PUBLIC_*`는 빌드 인자(브라우저에 박히는 공개 값만).
- `docker-compose.yml`: 백엔드는 `.env`를 읽고, 컨테이너 안에서는 `CHROMA_HOST=chroma`로 compose의 ChromaDB에 붙는다(Chroma Cloud 키는 비워 씀). Supabase는 compose 밖: 로컬 `supabase start` 스택을 쓰면 `.env.docker.local`(gitignore됨)에 `SUPABASE_URL=http://host.docker.internal:54321`처럼 컨테이너용 주소만 덮어쓴다. 클라우드면 `.env` 그대로.
- 호스트 포트는 `CHROMA_HOST_PORT` · `BACKEND_HOST_PORT` · `FRONTEND_HOST_PORT`로 바꾼다(앱 설정 `CHROMA_PORT`와 이름이 겹치지 않게 따로 둠).
- 빌드 없이 GHCR 이미지로 띄우기는 아래 "GHCR 이미지".

밤 시험(2026-10-08): 다른 project 이름(`ws9test`)과 호스트 포트 18000 · 18002로 화면 이미지 빌드 → 화면 200 응답 · ChromaDB heartbeat · `chromadb-client`로 컬렉션 만들기/넣기/지우기 확인. 백엔드 이미지는 `main.py`가 아직 없어 임시 `main.py`(/health만)로 Dockerfile 동작(uv sync · uvicorn · `LOG_TO_FILE=1`)만 확인했다. 시험 컨테이너 · 볼륨 · 이미지는 지웠다.

실제 백엔드 시험(2026-10-08, `v8check` · 18000/18001/18002): ChromaDB heartbeat, `/health` · `/ontology`, 시험용 계정으로 `/me` · `/universe`(하늘 데모 29편) · `/diary`, CORS, 화면 로그인 → 우주 화면, `logs/agent_flow_YYYYMMDD.log`에 원문 없음까지 통과. 결과 표는 [docs/docker-verify.md](../docs/docker-verify.md).

로컬 개발(Docker 없이 코드 직접): `scripts/start.sh`(Supabase 로컬 스택 · `my-universe-chroma` 컨테이너 · 백엔드 8001 `--reload` · 화면 3000) / `scripts/stop.sh`.

**로컬 포트 노출(보안 검토 M10)**: compose 의 세 포트는 `127.0.0.1`에만 묶었다(같은 와이파이의 다른 기기에서 열 수 없음). 한계: 로컬 Supabase 스택(54321 API · 54322 DB · 54323 Studio …)은 Supabase CLI(v2.75)에 바인드 주소 설정이 없어 모든 인터페이스에 열리고, DB 비밀번호는 공개된 기본값이다. 로컬 개발용 `my-universe-chroma`(`scripts/dev_up.sh` · `scripts/start.sh`)도 `127.0.0.1:8000`에만 연다. 그래도 Supabase 스택이 열려 있으므로 **실제 일기는 로컬 스택에 넣지 않는다**(가상 인물 데이터만). 학교 · 카페 와이파이에서는 `supabase stop`으로 꺼 두거나 macOS 방화벽(설정 → 네트워크 → 방화벽)을 켠다.

**DB 권한(보안 검토 H1)**: 마이그레이션 `20261009000000_v8_security.sql`이 anon · authenticated 의 표 · 시퀀스 · 함수 권한을 모두 거두고(앞으로 만들 표도 기본 권한 없음), 백엔드는 PostgREST 가 모르는 역할 `app_user`로 `set local role` 한다. 화면은 Supabase 를 로그인에만 쓰므로 영향이 없다. 로컬 스택은 `supabase migration up --local`, 클라우드는 `supabase db push`로 같이 적용된다. 새 표를 만들면 `app_user`용 RLS 정책(`own_app`)도 같이 만든다.

### GHCR 이미지

`.github/workflows/main.yml`(Actions 이름 `ghcr`, 2026-10-08)이 master push 와 수동 실행(Actions → ghcr → Run workflow) 때 이미지 3개를 만들어 GHCR 에 올린다. 문서(`*.md` · `docs/`)만 바뀐 push 는 건너뛰고, 연달아 push 하면 앞 실행을 멈춘다. 인증은 `GITHUB_TOKEN`(`contents: read` · `packages: write`)만 — PAT 없음. metadata-action 이 붙이는 `org.opencontainers.image.source` 라벨(이 저장소)로 패키지가 저장소에 연결되고 저장소 접근 권한을 따른다. 빌드 캐시는 GitHub Actions 캐시(`type=gha`, 이미지별).

| 이미지 | Dockerfile | 태그 |
| --- | --- | --- |
| `ghcr.io/lumiere001/my-universe-backend` | `Dockerfile` | `latest` · `sha-<커밋 7자리>` |
| `ghcr.io/lumiere001/my-universe-frontend` | `infra/frontend/Dockerfile` | 〃 |
| `ghcr.io/lumiere001/my-universe-chroma` | `infra/chroma/Dockerfile`(`chromadb/chroma:1.5.9` + 라벨) | 〃 |

```bash
docker login ghcr.io -u Lumiere001     # 비밀번호 칸에 읽기 토큰(아래)
docker compose -f docker-compose.yml -f docker-compose.ghcr.yml pull && docker compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d
scripts/stop_docker.sh                 # 끄기(같은 project 이름이라 그대로 됨)
```

- `docker-compose.ghcr.yml`은 세 서비스의 `image`만 GHCR 것으로 바꾸고 `build`를 지운다(`!reset`). 받기에 실패하면 로컬 빌드로 넘어가지 않고 멈춘다. 기본(`scripts/start_docker.sh`)은 지금처럼 로컬 빌드. 화면 이미지가 부르는 백엔드 주소는 빌드 때 박히므로(`DOCKER_API_BASE`, 기본 `http://localhost:8001`) `BACKEND_HOST_PORT`는 바꾸지 않는다.
- 이미지는 GitHub 러너(amd64)에서 만든다. Apple Silicon 맥은 `platform: linux/amd64`로 Docker Desktop 에뮬레이션에서 돈다(느릴 수 있음).
- 비공개 패키지라 받으려면 `docker login ghcr.io`가 필요하다. 토큰: GitHub Settings → Developer settings → Personal access tokens **(classic)** → `read:packages`만(GHCR 은 classic 토큰만 받는다).
- 공개로 바꿀지는 동규가 정한다: `https://github.com/users/Lumiere001/packages/container/<이미지 이름>/settings` → Danger Zone → Change visibility. 공개하면 로그인 없이 받지만 **다시 비공개로 못 돌리고**(GitHub 문서), 백엔드 이미지 안의 코드(`main.py` · `app/`)도 누구나 받게 된다. 화면 이미지의 anon 키는 원래 브라우저에 보이는 공개 값이다.
- 화면 이미지는 빌드할 때 값이 박힌다. 저장소 Settings → Secrets and variables → Actions 에 넣는다(동규):

| 이름 | 종류 | 화면 빌드 인자 | 없으면 |
| --- | --- | --- | --- |
| `DOCKER_API_BASE` | Variable | `NEXT_PUBLIC_API_BASE` | `http://localhost:8001` |
| `SUPABASE_URL` | Variable | `NEXT_PUBLIC_SUPABASE_URL` | 비움 |
| `SUPABASE_ANON_KEY` | Secret | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | 비움 |

비어 있어도 빌드는 되지만 화면이 "로그인 설정이 없어요"를 보인다(`NEXT_PUBLIC_DEV_LOGIN=0`이라 시험용 계정 칸도 없음). 백엔드(`.env`, 로컬 스택이면 `.env.docker.local`)도 같은 Supabase 를 가리켜야 로그인 토큰이 맞는다. 값을 넣거나 바꾼 뒤 Run workflow 로 다시 만든다.

비용: 비공개 저장소라 실행마다 Actions 무료 분을 쓴다(작업 3개, 화면이 가장 김). GHCR 저장 · 전송은 지금 무료다(GitHub 문서, 바뀌면 한 달 전 알림). `sha-` 버전이 push 마다 쌓이니 가끔 패키지 페이지에서 지운다.

## 4. 운영 규칙

### 원문 없는 로그

- 남기는 것: 시각, 기록 id, 단계(`safety` … `save`), 걸린 시간, 상태, 오류 코드(영문), 설정 번호, 추정 비용, 개수.
- 남기지 않는 것: 일기 글 · 제목 · 인용 · 요약 · 사람 이름 · 되고 싶은 모습 문장 · 토큰 · 키. 예외 메시지는 원문이 섞일 수 있으니 **예외 종류(클래스 이름)와 우리 오류 코드만** 남긴다.
- Vercel은 표준 출력(보관 1시간), Docker · 로컬은 `logs/agent_flow_YYYYMMDD.log`(`LOG_TO_FILE=1`).
- 배포 확인 · 리허설 날 Vercel Logs에서 실제로 원문이 안 보이는지 눈으로 확인한다(MORNING ⑥ · ⑦).

### 비용 한도

| 어디 | 누가 | 무엇 |
| --- | --- | --- |
| Upstage 콘솔 | 동규 | Billing에서 한도 · 알림 메뉴가 있으면 월 한도를 건다(공개 문서에서 확인 못 함 — 콘솔에서 확인). 없으면 리허설 다음 날 · 매주 잔액을 본다. Studio 크레딧 승인 범위 $50 |
| 앱(백엔드) | WS5 | **지금은 운영 상한 없음 · 가입은 구글 로그인한 누구나**(2026-10-08 동규: 실제 배포 · 수익화를 생각할 때 사용량과 비즈니스 모델을 보고 정함, plan §2-9). 손잡이만 남김: 사용자당 하루 일기 수 `DAILY_ENTRY_LIMIT`, 이달 추정 비용 `MONTHLY_COST_CAP_USD`(달러), 기록당 이어 하기 `RESUME_LIMIT` — 넣지 않거나 0이면 상한 없음, 넣으면 넘을 때 처리 멈추고 안내(429). `ALLOWED_EMAILS`를 넣으면 목록 밖 계정은 403. 그때까지 전체 비용은 Upstage 콘솔 · `/stats`(이달 추정 비용)로 본다 |
| Vercel | — | Hobby는 청구 없음. 한도를 넘으면 함수가 멈춘다 |
| Supabase | — | Free 플랜은 청구 없음(500MB DB). 일주일 안 쓰면 일시 정지되니 매일 쓰면 문제 없음 |
| Chroma Cloud | 동규 | Starter $0 + 사용량, 무료 크레딧 $5. 콘솔 Billing에서 사용량 확인 |

### 오류 알림 (추천 하나): GitHub Actions 하루 한 번 `/health`

`.github/workflows/health.yml`(= `deploy/health.yml` 사본, 2026-10-08 넣음)을 push 하고(MORNING ①), 저장소 Settings → Secrets and variables → Actions → **Variables**에 `API_URL`(백엔드 주소) · `WEB_URL`(화면 주소)을 넣으면 켜진다. 변수가 없으면 아무것도 하지 않는다. 매일 09:00(KST)에 두 주소를 부르고, 실패하면 GitHub이 **예약 실행 실패 메일**을 보낸다(일정을 마지막으로 바꾼 사람에게). 추가 계정 · 비용 없음.

- 이게 잡는 것: 배포 깨짐, 환경변수 빠짐, 서버 다운. 못 잡는 것: 일기 처리 중 Studio 오류 → 그건 화면의 오류 이벤트와 피드백("불편한 점 한 줄"), `/stats`로 본다.
- Vercel 자체 알림(Observability Alerts)은 Pro 이상이라 쓰지 않는다.

## 5. 환경변수 이름 (값은 동규가 Vercel에)

백엔드(`my-universe-api`) — 실제 이름(`app/core/config.py` · `.env.example`, 2026-10-08 확인):

| 이름 | 값 |
| --- | --- |
| `UPSTAGE_API_KEY` | Upstage 콘솔 키 |
| `RECORD_AGENT_ID`, `OBSERVE_AGENT_ID` | Studio 에이전트 ID(1차와 같음) |
| `V8_RECORD_CONFIG_ID`, `V8_OBSERVE_CONFIG_ID` | `2` (1판 `RECORD_CONFIG_ID=1`은 Streamlit 데모용으로 그대로) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Supabase Project Settings → API Keys(**Legacy** `anon`, `eyJ…` 모양) |
| `DATABASE_URL` | Supabase Connect → **Transaction pooler**(포트 6543) 주소. 서버리스라 직접 연결 대신 풀러 |
| `DIARY_ENC_KEY` | 일기 암호화 키(32바이트 base64, MORNING ⑤의 명령으로 만듦). Vercel과 비밀번호 관리자 두 곳에만 둔다(잃으면 저장된 글을 못 염) |
| `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE` | Chroma Cloud(이 이름은 Chroma `CloudClient`가 그대로 읽는 이름) |
| `FRONTEND_ORIGIN` | 화면 주소 `https://<화면>.vercel.app` (CORS) |
| `DAILY_ENTRY_LIMIT`, `MONTHLY_COST_CAP_USD`, `RESUME_LIMIT` | **넣지 않음** — 운영 상한은 나중에(넣지 않거나 `0`이면 상한 없음, §4) |
| `ALLOWED_EMAILS` | **넣지 않음** — 구글 로그인한 누구나. 넣으면(쉼표 목록) 목록 밖은 403 `not_allowed` |
| `SUPABASE_SERVICE_ROLE_KEY` | 계정 지우기(`DELETE /me`)에서만 쓰는 Supabase 서비스 키(**Legacy** `service_role`, `eyJ…` 모양. 코드는 새 형식 `sb_secret_…`도 받는다 — `apikey` 헤더로만 보냄, 2026-10-08 고침). 백엔드에만, 화면에는 넣지 않음 |
| 넣지 않음 | `LOG_TO_FILE`(기본 `0` = 표준 출력), `CHROMA_HOST` · `CHROMA_PORT`, `RECORD_CONFIG_ID` · `OBSERVE_CONFIG_ID`(1차용), `API_DOCS`(없으면 `/docs` 꺼짐), `DEV_TEST_PASSWORD`(로컬 시험 전용), `PHOTO_READ_MODEL`(없으면 사진 글자 읽기 `document-parse`, `ocr` 로 되돌릴 때만 넣음) |

화면(`my-universe`): `NEXT_PUBLIC_API_BASE`(백엔드 주소), `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_DEV_LOGIN=0`, `NEXT_PUBLIC_MOCK=0` (`infra/frontend/.env.example`과 같음).

로컬 · Docker는 `CHROMA_HOST` · `CHROMA_PORT`(ChromaDB 컨테이너), Chroma Cloud 키가 있으면 클라우드로 붙는 방식으로 WS5가 고른다(compose는 컨테이너 안에서 `CHROMA_API_KEY`를 비워 로컬 ChromaDB를 쓰게 함).

## 6. WS5 · 오케스트레이터에게 (이 브랜치 밖 파일)

- `pyproject.toml`: `[tool.vercel]` `entrypoint = "main:app"` — 넣음(2026-10-08 아침, MORNING ①).
- `.env.example`: §5 이름 들어감(완료).
- DB 연결: `app/repository/tables.py`가 `prepare_threshold=None`으로 연결(완료).
- 실행 중에 읽는 데이터 파일: `data/ops/domain_aliases_*.json` · `topic_center_*.json`(`app/agents/tools.py` `sun_vectors`). `.dockerignore` · `Dockerfile` COPY · `.vercelignore` · `vercel.json excludeFiles`에 반영(완료). 새로 읽는 파일이 생기면 네 곳을 같이 고친다. 파일이 없으면 조용히 빈 값이 되니 주의.
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
- Google OAuth 게시 · 검증(게시하면 구글 계정 누구나, 비민감 범위만이면 앱 검증 필수 아님, 로고를 올리면 검증 · 미검증이면 도메인만 보임, 경고는 민감 · 제한 범위만): https://support.google.com/cloud/answer/15549945 · https://support.google.com/cloud/answer/13463073 · https://support.google.com/cloud/answer/15549049 · https://developers.google.com/identity/protocols/oauth2/production-readiness/overview
- ChromaDB 이미지 태그 `chromadb/chroma:1.5.9`(= `chromadb-client` 1.5.9): https://hub.docker.com/r/chromadb/chroma
- GHCR(`GITHUB_TOKEN`으로 올리면 저장소에 연결, `org.opencontainers.image.source` 라벨, classic 토큰만): https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- 패키지 공개 전환(Danger Zone → Change visibility, 공개하면 다시 비공개 불가): https://docs.github.com/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility
- GHCR 저장 · 전송 지금 무료: https://docs.github.com/billing/concepts/product-billing/github-packages
