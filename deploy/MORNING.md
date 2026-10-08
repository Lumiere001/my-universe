# 아침 배포 순서 (동규용)

밤에 에이전트는 배포 직전까지만 준비했다(설정 파일 · 스크립트 · 이 문서). 계정 · 클라우드 프로젝트 · 키 입력 · push · 배포는 동규만 한다.
왜 이렇게 했는지는 [README.md](README.md). 환경변수 이름은 실제 코드(`app/core/config.py`, `.env.example`, `infra/frontend/.env.example`)와 맞췄다(2026-10-08 다시 확인). Docker 3개를 실제 백엔드로 띄워 본 결과는 [docs/docker-verify.md](../docs/docker-verify.md).

위에서부터 그대로 따라 하면 된다. 다 하면 약 **2시간**(리허설 하루는 따로).

| 순서 | 할 일 | 시간 |
| --- | --- | --- |
| ① | push(pyproject 두 줄 · health 워크플로는 끝남) | 5분 |
| ② | Supabase 새 프로젝트 · db push · Data API 막힘 확인 · Email 끄기 | 20분 |
| ③ | 구글 로그인(OAuth), 앱 게시(누구나 로그인) | 15분 |
| ④ | Chroma Cloud | 10분 |
| ⑤ | Vercel 두 프로젝트(백엔드 · 화면) | 30분 |
| ⑥ | 배포 확인 · 오류 알림 켜기 | 15분 |
| ⑦ | 리허설(동규 하루 써 보기) | 하루(확인은 30분) |
| ⑧ | 현호 초대(화면 주소 보내기) | 5분 |

미리 정할 것: 화면 프로젝트 이름 `my-universe`, 백엔드 프로젝트 이름 `my-universe-api`.
→ 주소가 `https://my-universe.vercel.app` · `https://my-universe-api.vercel.app`이 된다(이름이 이미 쓰이고 있으면 Vercel이 다른 주소를 준다. 그때는 아래에 나오는 주소를 실제 주소로 바꿔 넣는다).
이 문서에서 `<ref>` = Supabase 프로젝트 ref.

**키 다루는 법:** 키는 대시보드에서 복사해 Vercel 칸에 바로 붙여 넣는다. 파일 · 메모 · 채팅에 적지 않는다. 예외는 `DIARY_ENC_KEY`와 DB 비밀번호: 이 둘은 **비밀번호 관리자에도** 보관한다(잃으면 되돌릴 수 없음).

---

## ① pyproject 두 줄 · health 워크플로 · push (5분)

- 무슨 일: Vercel 진입점을 적고, 오류 알림 워크플로를 제자리에 두고, 밤에 로컬 master에 합친 커밋을 GitHub에 올린다.
- 왜: Vercel이 GitHub 저장소에서 가져와 배포한다. 진입점을 적어 두면 루트의 1차 `app.py`(Streamlit)와 헷갈릴 일이 없다(공식: https://vercel.com/docs/frameworks/backend/fastapi 의 `tool.vercel.entrypoint`, 2026-10-08 확인). 워크플로 파일은 `.github/workflows/`에 있어야 GitHub이 돌린다(`deploy/health.yml`에서 복사해 둠).
- **끝남(2026-10-08 오케스트레이터):** `pyproject.toml` 맨 아래 두 줄(`[tool.vercel]` · `entrypoint = "main:app"`, `uv.lock`은 바뀌지 않음)과 `.github/workflows/health.yml`(= `deploy/health.yml` 사본)을 master에 커밋했다.
- 할 일(남은 것): 확인하고 push.

```bash
cd ~/Projects/my-universe
uv run --frozen pytest -q          # 462 passed, 5 skipped 인지(5개는 로컬 Supabase 가 꺼져 있을 때 건너뛰는 DB 시험. 켜져 있으면 467 passed)
git status                         # 깨끗한지
git log --oneline -15              # 밤 작업 커밋 확인
git push origin master
```

- push 가 "workflow scope" 때문에 거절되면: `gh auth refresh -s workflow` 뒤 다시 push.

## ② Supabase 새 프로젝트 (20분)

- 무슨 일: 일기 · 생각 · 관계 · 사람 · 설정을 담을 DB와 로그인을 만들고, 표와 보안 설정(마이그레이션 2개)을 올린다.
- 왜: 무료 플랜은 조직마다 프로젝트 수 한도가 있다. 밤에 `bus-cignal-prod`를 일시 정지해 자리를 비워 뒀다. 보안 마이그레이션이 있어야 화면에 공개되는 anon 키로 표를 직접 고치는 길(보안 검토 H1)이 막힌다.
- 할 일:
  1. `supabase projects list`로 `bus-cignal-prod`가 일시 정지(INACTIVE/PAUSED)인지 확인. 아니면 대시보드 → 그 프로젝트 → Project Settings → General → Pause project.
  2. https://supabase.com/dashboard → New project → 이름 `my-universe` → Database Password는 Generate(**비밀번호 관리자에 보관**) → **Region: Northeast Asia (Seoul)** → Free → Create.
  3. 만들어지면 주소 `https://supabase.com/dashboard/project/<ref>`에서 `<ref>`를 확인하고:

```bash
cd ~/Projects/my-universe
supabase link --project-ref <ref>     # DB 비밀번호를 물어보면 2에서 만든 것
supabase db push                      # 마이그레이션 2개를 클라우드에 적용
supabase migration list               # Local · Remote 두 줄 모두 20261008000000 · 20261009000000 이면 끝
```

  - `db push`가 올리는 것: `20261008000000_v8_init.sql`(표 15개 · RLS), `20261009000000_v8_security.sql`(anon · authenticated 의 표 권한을 모두 거두고, 백엔드 전용 역할 `app_user`를 만들고, 위기 · 돌봄 표시를 암호문 안으로 옮김). 오류가 나면 멈추고 오류 문구를 적어 둔다(키 · 비밀번호는 빼고).

  4. Data API 막힘 확인. 대시보드 → Project Settings → **API Keys** 에서 `anon` 키를 복사한 뒤(클립보드에 둔 채):

```bash
curl -s -w "\n%{http_code}\n" "https://<ref>.supabase.co/rest/v1/runs?select=*" -H "apikey: $(pbpaste)"
# 기대: {"code":"42501", ... "permission denied for table runs"} 와 401  (로컬에서 같은 결과 확인함)
# 200 과 [] 가 나오면 보안 마이그레이션이 안 들어간 것 → 3의 db push 를 다시 본다
```

  5. 값 찾는 곳(⑤에서 Vercel에 바로 붙여 넣음, 다른 데 적지 않기):
     - Project URL(`SUPABASE_URL`): Project Settings → Data API(또는 API) → Project URL. 모양은 `https://<ref>.supabase.co`.
     - Project Settings → API Keys → **Legacy API Keys** 탭: `anon` `public`(`SUPABASE_ANON_KEY`), `service_role`(`SUPABASE_SERVICE_ROLE_KEY`, **백엔드에만** — 계정 지우기 `DELETE /me` 전용. 화면 프로젝트 · `NEXT_PUBLIC_*`에는 절대 넣지 않는다). 둘 다 `eyJ`로 시작하는 긴 값이다.
       - 왜 Legacy: 로컬 시험을 Legacy 모양(JWT) 키로 했다. 코드는 두 형식을 다 받는다(2026-10-08 고침: `eyJ…` 키는 `apikey` + `Authorization: Bearer`, 새 `sb_secret_…` 키는 `apikey` 헤더로만). Legacy 탭이 없으면 새 Secret key를 넣고, 배포 확인(⑥)에서 시험 계정으로 계정 지우기가 되는지 꼭 본다(새 형식은 실제 Supabase에서 아직 시험하지 않음).
     - 위쪽 **Connect** 버튼 → Connection string → **Transaction pooler**(포트 6543) URI의 `[YOUR-PASSWORD]`를 DB 비밀번호로 바꾼 것(`DATABASE_URL`). Vercel은 서버리스라 직접 연결 대신 풀러를 쓴다(코드는 풀러용으로 `prepare_threshold=None`).
  6. Authentication → Sign In / Providers → **Email** → 끄기(Disable). 로그인은 구글 하나라 이메일 가입 길을 닫는다(전체 "Allow new users to sign up"은 켜 둔다 — 끄면 아무도 구글로 처음 들어올 수 없다. 지금은 구글 계정이면 누구나 쓴다: 허용 목록 없음, plan §2-9).

## ③ 구글 로그인(OAuth) (15분)

- 무슨 일: Supabase 로그인에 구글을 연결한다.
- 왜: v8 로그인은 구글 로그인 하나(WS0 결정 4). 가입은 허용 목록 없이 구글 계정이면 누구나(2026-10-08 아침 동규 결정, plan §2-9) → 동의 화면을 외부(External)로 만들고 **게시**한다(테스트 사용자 등록 없음).
- 할 일:
  1. https://console.cloud.google.com → 새 프로젝트 `my-universe`.
  2. Google Auth Platform(= OAuth 동의 화면) → 시작하기 → 앱 이름 `나의 우주`, 지원 이메일 = 동규 → 대상 **외부(External)** → 저장.
     - 데이터 액세스(범위): 기본 정보 `email` · `profile` · `openid`만(모두 비민감 범위). 다른 범위 추가하지 않기.
     - 브랜딩: **로고는 올리지 않는다**(게시한 외부 앱에 로고를 올리면 Google 검증을 거쳐야 한다).
     - 대상(Audience) → **앱 게시(Publish app)** → 확인 → 게시 상태가 **프로덕션 단계(In production)**. 이러면 구글 계정이 있는 누구나 로그인한다.
     - 검증 없이 되는 이유: 비민감 범위만 쓰는 앱은 앱 검증이 필수가 아니다. 브랜드 검증을 안 하면 구글 로그인 화면에 앱 이름 · 로고 대신 도메인만 보인다(정상). "확인되지 않은 앱" 경고는 민감 · 제한 범위를 쓸 때만 나온다. 공식 문서(2026-10-08 확인): https://support.google.com/cloud/answer/15549945 (게시 = 누구나) · https://support.google.com/cloud/answer/13463073 (비민감 범위는 검증 필수 아님) · https://support.google.com/cloud/answer/15549049 (로고 → 검증, 미검증이면 도메인만) · https://developers.google.com/identity/protocols/oauth2/production-readiness/overview (경고는 민감 · 제한 범위만).
  3. 클라이언트 → 클라이언트 만들기 → 유형 **웹 애플리케이션** →
     - 승인된 JavaScript 원본: `https://my-universe.vercel.app` (+ 로컬 시험용 `http://localhost:3000`)
     - 승인된 리디렉션 URI: `https://<ref>.supabase.co/auth/v1/callback`
     - 만들기 → 클라이언트 ID · 클라이언트 보안 비밀이 나온다(창을 닫기 전에 4로).
  4. Supabase 대시보드 → Authentication → Sign In / Providers → **Google** → Enable → Client ID · Client Secret 붙여 넣기 → Save.
  5. Authentication → URL Configuration:
     - Site URL: `https://my-universe.vercel.app`
     - Redirect URLs: `https://my-universe.vercel.app/**` , `http://localhost:3000/**`

## ④ Chroma Cloud (10분)

- 무슨 일: 생각 벡터(지난 생각 고르기)를 담을 저장소를 만든다.
- 왜: 벡터 저장은 ChromaDB 하나(WS0 결정 3). 로컬 · Docker는 컨테이너, 배포는 Chroma Cloud. Starter $0 + 사용량, 무료 크레딧 $5. 벡터는 가명 글로 만들고 글자는 넣지 않는다.
- 할 일:
  1. https://www.trychroma.com → Sign up(구글 계정 가능).
  2. Create database → 이름 `my-universe` (지역은 기본 AWS us-east-1).
  3. 그 데이터베이스의 Settings/Connect 화면에서 **API key 만들기** → 키(`CHROMA_API_KEY`), **Tenant ID**(`CHROMA_TENANT`), 데이터베이스 이름(`CHROMA_DATABASE` = `my-universe`). 컬렉션은 백엔드가 처음 쓸 때 `thoughts`로 만든다(`CHROMA_COLLECTION`, 넣지 않아도 됨).
  4. Billing에서 사용량 알림이 있으면 켠다.

## ⑤ Vercel 두 프로젝트 (30분)

- 무슨 일: 같은 저장소를 두 번 가져온다. 백엔드(FastAPI, 저장소 루트)와 화면(Next.js, `infra/frontend`).
- 왜: 화면이 백엔드를 절대 주소로 부르는 구조라 코드 변경이 없고, 한 프로젝트로 묶는 Services는 아직 Beta다(README §1).
- 먼저 암호화 키 만들기:

```bash
python3 -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

  결과를 **비밀번호 관리자에 "나의 우주 DIARY_ENC_KEY (배포)"로 먼저 저장**하고, 그다음 Vercel `DIARY_ENC_KEY` 칸에 붙여 넣는다. 그 밖(파일 · 메모 · 채팅)에는 두지 않는다. 이 키를 잃거나 바꾸면 저장된 일기를 아무도 못 연다(보안 검토 L12). 로컬 `.env.local`의 키와 다른 새 키여야 한다.

### 5-1. 백엔드 `my-universe-api`

1. https://vercel.com/new → GitHub `my-universe` Import → Project Name `my-universe-api`.
2. Root Directory: `./`(그대로). Framework Preset: **FastAPI**(자동으로 안 잡히면 직접 고름). Build/Install 명령은 비워 둔다(uv + `uv.lock` 자동).
3. Environment Variables(값은 ②③④에서, 모두 Production · Preview):

| 이름 | 값 |
| --- | --- |
| `UPSTAGE_API_KEY` | Upstage 콘솔 키 |
| `RECORD_AGENT_ID` | 기록 Agent ID (로컬 `.env`와 같은 값) |
| `OBSERVE_AGENT_ID` | 관측 Agent ID (로컬 `.env`와 같은 값) |
| `V8_RECORD_CONFIG_ID` | `2` |
| `V8_OBSERVE_CONFIG_ID` | `2` |
| `SUPABASE_URL` | ② Project URL |
| `SUPABASE_ANON_KEY` | ② Legacy `anon` 키 |
| `SUPABASE_SERVICE_ROLE_KEY` | ② Legacy `service_role` 키(계정 지우기 전용. 없으면 설정 화면의 "계정과 모든 기록 지우기"가 503) |
| `DATABASE_URL` | ② Transaction pooler URI(비밀번호 넣은 것) |
| `DIARY_ENC_KEY` | 위 명령 결과(비밀번호 관리자에도 보관) |
| `CHROMA_API_KEY` · `CHROMA_TENANT` · `CHROMA_DATABASE` | ④ |
| `FRONTEND_ORIGIN` | `https://my-universe.vercel.app` (끝에 `/` 없이) |

넣지 않는 것: `ALLOWED_EMAILS`(넣지 않음 — 구글 로그인한 누구나 쓴다. 나중에 가입 범위를 정할 때 쓰는 손잡이), `DAILY_ENTRY_LIMIT` · `MONTHLY_COST_CAP_USD` · `RESUME_LIMIT`(넣지 않음 — 운영 상한은 나중에. 넣지 않으면 상한 없음. 둘 다 plan §2-9), `API_DOCS`(없으면 `/docs` · `/openapi.json`이 꺼짐 — 배포는 끈 채로), `LOG_TO_FILE`(기본 `0` = 표준 출력 → Vercel Logs), `CHROMA_HOST` · `CHROMA_PORT`(`CHROMA_API_KEY`가 있으면 Chroma Cloud를 씀), `RECORD_CONFIG_ID` · `OBSERVE_CONFIG_ID`(1차 Streamlit용), `DEV_TEST_PASSWORD`(로컬 시험 전용), `SUPABASE_AUTH_EXTERNAL_GOOGLE_*`(로컬 Supabase 전용 — 클라우드는 ③-4 대시보드에 넣음).

4. Deploy → 빌드 로그에서 Python 함수가 `main.py`로 잡혔는지 본다(①의 `entrypoint = "main:app"`. `vercel.json`의 함수 키도 `main.py`라 다르게 잡히면 빌드가 실패해 드러난다).
5. Settings → Functions에서 Region이 Seoul(icn1)인지 확인(`vercel.json`의 `regions`).

### 5-2. 화면 `my-universe`

1. https://vercel.com/new → 같은 저장소 다시 Import → Project Name `my-universe`.
2. **Root Directory: `infra/frontend`** → Framework Preset: Next.js(자동).
3. Environment Variables:

| 이름 | 값 |
| --- | --- |
| `NEXT_PUBLIC_API_BASE` | `https://my-universe-api.vercel.app` |
| `NEXT_PUBLIC_SUPABASE_URL` | ② Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ② Legacy `anon` 키(service_role 아님) |
| `NEXT_PUBLIC_DEV_LOGIN` | `0` |
| `NEXT_PUBLIC_MOCK` | `0` |

4. Deploy.
5. 실제 주소가 `my-universe.vercel.app`과 다르면: 백엔드 `FRONTEND_ORIGIN`, ③-3 JavaScript 원본, ③-5 Site URL · Redirect URLs를 실제 주소로 고치고 백엔드를 Redeploy(Deployments → 최신 → ⋯ → Redeploy). 백엔드 주소가 다르면 화면 `NEXT_PUBLIC_API_BASE`를 고치고 화면을 Redeploy(`NEXT_PUBLIC_*`는 빌드 때 박힘).
6. (선택) Settings → Functions → Region → Seoul(icn1).

## ⑥ 배포 확인 · 오류 알림 켜기 (15분)

- 무슨 일: 배포가 실제로 돌고, 막아야 할 것이 막혔는지 본다. 그다음 하루 한 번 자동 확인을 켠다.
- 왜: 리허설 전에 설정 실수(키 빠짐 · 주소 틀림 · 문서 열림)를 잡는다.
- 할 일:

```bash
curl -s https://my-universe-api.vercel.app/health
# 기대: {"status":"ok","version":"0.8.0"}
curl -s -o /dev/null -w "%{http_code}\n" https://my-universe-api.vercel.app/docs
# 기대: 404 (API 문서 꺼짐. 200 이면 API_DOCS 가 들어간 것 → 지우고 Redeploy)
curl -s -o /dev/null -w "%{http_code}\n" https://my-universe-api.vercel.app/me
# 기대: 401 (로그인 없이는 못 씀)
```

- [ ] `https://my-universe.vercel.app` → 구글 로그인 → 첫 화면이 뜬다(오류 문구 없이. 구글 화면에 "나의 우주" 대신 도메인이 보여도 정상 — ③-2).
- [ ] (가능하면) 다른 구글 계정으로 로그인 → 막히지 않고 첫 화면이 뜨고, 동규의 기록은 하나도 보이지 않는다.
- [ ] 설정 → 로그아웃 → 다시 로그인 화면.
- [ ] Vercel → `my-universe-api` → Logs: 한 줄짜리 JSON(`event` · `path` · `http` · `ms`)만 보이고 키 · 이름 · 글은 없다.

오류 알림 켜기(①에서 올린 `.github/workflows/health.yml`):
GitHub 저장소 → Settings → Secrets and variables → Actions → **Variables** 탭 → `API_URL` = `https://my-universe-api.vercel.app`, `WEB_URL` = `https://my-universe.vercel.app`. Actions 탭 → health → Run workflow로 한 번 돌려 초록인지 본다. 이후 매일 09:00(KST)에 두 주소를 확인하고, 실패하면 GitHub이 메일을 보낸다. 변수가 없으면 아무것도 하지 않는다.

## ⑦ 리허설(동규 하루 써 보기)

- 무슨 일: 현호보다 먼저 하루 동안 실제로 써 본다.
- 왜: 휴대폰 · PC, 끊김, 비용, 로그를 실제 배포에서 확인한다.
- 할 일: 글은 가상 인물 글이나 Studio로 보내도 괜찮은 글로 쓴다. 휴대폰 · PC 둘 다.

- [ ] 구글 로그인 → 첫 화면 → 마음 날씨 질문이 첫 만남에만 나온다.
- [ ] 일기 쓰기 → 진행 단계가 하나씩 바뀐다(SSE) → 약 1분 뒤 결과 카드(생각 · 한마디 · 다음 질문).
- [ ] 쓰는 중에 비행기 모드 → 다시 켜기 → "이어서 하기"로 끝까지 간다(새로고침해도 이어서 하기가 보인다).
- [ ] 우주: 해 · 작은 별 · 행성이 보이고, 행성을 누르면 영역을 넘는 선이 보인다. 점선에 맞아요/아니에요가 있다.
- [ ] 버튼: 맞아요/아니에요, 좋아요/별로, 지켰어요/그만둘래요, 불편한 점 한 줄, 오늘은 살살 → 다시 열어도 반영돼 있다.
- [ ] 사람 목록: 일기에 나온 이름이 자동 등록, 지우기 하면 글에서 관계 말로 바뀐다.
- [ ] 말투 바꾸기(팩폭은 경고 확인 뒤에만).
- [ ] 위기 문장(예: 가상 문장 "다 끝내고 싶다")을 쓰면 평소 결과 카드가 나오고, 한마디는 위로(팩폭이어도 다정하게) + 그 아래 안부 한 줄. 따로 뜨는 화면 · 109 · 마들랜 · 119 · 112 안내는 없다(시험 단계, 2026-10-08 동규 결정).
- [ ] 일기 지우기 → 우주에서도 사라진다.
- [ ] Vercel → `my-universe-api` → Logs: 일기 글 · 인용 · 이름이 **한 줄도 안 보인다**. 오류(빨간 줄)가 있으면 오류 코드를 적어 둔다(보관 1시간).
- [ ] 다음 날: Upstage 콘솔 사용량 · `/stats`의 이달 추정 비용(`month_cost_usd`)이 예상(글당 약 $0.10)과 맞는다. Chroma Cloud 사용량도 본다.
- (선택) 계정 지우기는 리허설 계정을 지우고 싶을 때만: 설정 맨 아래 "계정과 모든 기록 지우기" → '지우기' 입력. 되돌릴 수 없다.

## ⑧ 현호 초대 (5분)

- 무슨 일: 현호가 10/17부터 실제로 쓰게 한다.
- 왜: 동의 화면을 게시했고 허용 목록이 없어서(③-2, plan §2-9) 화면 주소만 보내면 된다. 현호 이메일을 어디에 등록할 일은 없다.
- 할 일:
  1. 현호에게 보내기: 주소 `https://my-universe.vercel.app`, 휴대폰은 브라우저 메뉴의 "홈 화면에 추가", 구글 로그인 화면에 "나의 우주" 대신 도메인이 보여도 정상(로고 · 브랜드 검증을 하지 않아서), 불편한 점은 결과 카드의 "불편한 점 한 줄"로.
  2. 기술 설명 문서 `docs/tech-explainer-v8.md`(10/16, WS10)를 같이 보낸다. 특히 1.3 "개인정보 약속"(가명 처리와 그 한계, 운영자가 기술적으로 풀 수 있다는 점)을 읽고 쓸지 정하게 한다.
