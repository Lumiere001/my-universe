# 아침 배포 순서 (동규용)

밤에 에이전트는 배포 직전까지만 준비했다(설정 파일 · 스크립트 · 이 문서). 계정 · 클라우드 프로젝트 · 키 입력 · push · 배포는 동규만 한다.
왜 이렇게 했는지는 [README.md](README.md). 환경변수 이름은 실제 코드(`app/core/config.py`, `.env.example`)와 맞췄다. Docker 3개를 실제 백엔드로 띄워 본 결과는 [docs/docker-verify.md](../docs/docker-verify.md).

미리 정할 것: 화면 프로젝트 이름 `my-universe`, 백엔드 프로젝트 이름 `my-universe-api`.
→ 주소가 `https://my-universe.vercel.app` · `https://my-universe-api.vercel.app`이 된다(이름이 이미 쓰이고 있으면 Vercel이 다른 주소를 준다. 그때는 아래에 나오는 주소를 실제 주소로 바꿔 넣는다).
이 문서에서 `<화면>` = 화면 주소, `<API>` = 백엔드 주소, `<ref>` = Supabase 프로젝트 ref.

---

## ① git push

- 무슨 일: 밤에 로컬 master에 합친 커밋을 GitHub에 올린다.
- 왜: Vercel이 GitHub 저장소에서 가져와 배포한다.
- 할 일:

먼저 `pyproject.toml` 맨 아래에 두 줄을 넣는다. Vercel이 진입점을 `main.py`의 `app`으로 확정한다(공식: https://vercel.com/docs/frameworks/backend/fastapi 의 `tool.vercel.entrypoint`). 없어도 `.vercelignore`가 1차 `app.py`를 빼서 `main.py`가 잡히지만, 적어 두면 헷갈릴 일이 없다.

```toml
[tool.vercel]
entrypoint = "main:app"
```

```bash
cd ~/Projects/my-universe
git add pyproject.toml && git commit -m "Vercel 진입점 main:app"
git status                  # 깨끗한지
git log --oneline -15       # 밤 작업 커밋 확인
git push origin master
```

(오류 알림을 켤 거면 `.github/workflows/health.yml`이 있는지 본다. 없으면 `mkdir -p .github/workflows && cp deploy/health.yml .github/workflows/` 후 커밋 · push. 켜는 건 ⑤ 끝에서.)

## ② Supabase 새 프로젝트

- 무슨 일: 일기 · 생각 · 관계 · 사람 · 설정을 담을 DB와 로그인을 만든다.
- 왜: 무료 플랜은 조직마다 프로젝트 수 한도가 있다. 밤에 `bus-cignal-prod`를 일시 정지해 자리를 비워 뒀다.
- 할 일:
  1. `supabase projects list`로 `bus-cignal-prod`가 일시 정지(INACTIVE/PAUSED)인지 확인. 아니면 대시보드 → 그 프로젝트 → Project Settings → General → Pause project.
  2. https://supabase.com/dashboard → New project → 이름 `my-universe` → Database Password는 Generate(비밀번호 관리자에 보관) → **Region: Northeast Asia (Seoul)** → Free → Create.
  3. 만들어지면 주소의 `https://supabase.com/dashboard/project/<ref>`에서 `<ref>`를 확인하고:

```bash
cd ~/Projects/my-universe
supabase link --project-ref <ref>     # DB 비밀번호를 물어보면 2에서 만든 것
supabase db push                      # supabase/migrations 의 표 · 권한(RLS)을 클라우드에 만든다(파일 2개, 아래 참고)
```

  4. 값 찾는 곳(⑤에서 Vercel에 바로 붙여 넣음, 다른 데 적지 않기):
     - Project Settings → API: Project URL(`SUPABASE_URL`), `anon` `public` 키(`SUPABASE_ANON_KEY`), `service_role` 키(`SUPABASE_SERVICE_ROLE_KEY`, **백엔드에만** — 계정 지우기 `DELETE /me` 전용. 화면 프로젝트 · `NEXT_PUBLIC_*`에는 절대 넣지 않는다).
     - 위쪽 **Connect** 버튼 → Connection string → **Transaction pooler**(포트 6543) URI의 `[YOUR-PASSWORD]`를 DB 비밀번호로 바꾼 것(`DATABASE_URL`). Vercel은 서버리스라 직접 연결 대신 풀러를 쓴다.

  5. `db push`는 `20261009000000_v8_security.sql`(보안 검토 H1)도 같이 적용한다: anon · authenticated 가 Data API(`/rest/v1`)로 표를 읽고 쓰지 못하게 권한을 거두고, 백엔드 전용 역할 `app_user`를 만든다. 확인(값은 ② anon 키):

```bash
curl -s -o /dev/null -w "%{http_code}\n" "https://<ref>.supabase.co/rest/v1/runs?select=*" -H "apikey: <anon 키>"   # 401 이면 막힘
```

  6. Authentication → Sign In / Providers → **Email** → 끄기(Disable). 로그인은 구글 하나라 이메일 가입 길을 닫는다(전체 "Allow new users to sign up"은 켜 둔다 — 끄면 현호가 구글로 처음 들어올 수 없다).

## ③ 구글 로그인(OAuth)

- 무슨 일: Supabase 로그인에 구글을 연결한다.
- 왜: v8 로그인은 구글 로그인 하나(WS0 결정 4). 동의 화면을 "테스트"로 두면 등록한 사람만 로그인할 수 있어 10/17엔 그게 맞다.
- 할 일:
  1. https://console.cloud.google.com → 새 프로젝트 `my-universe`.
  2. Google Auth Platform(= OAuth 동의 화면) → 시작하기 → 앱 이름 `나의 우주`, 지원 이메일 = 동규 → 대상 **외부(External)** → 저장.
     - 대상(Audience): 게시 상태 **테스트** 유지 → 테스트 사용자에 **동규 이메일 · 현호 이메일** 추가.
     - 데이터 액세스(범위): 기본 `openid` · `email` · `profile`만. 다른 범위 추가하지 않기.
  3. 클라이언트 → 클라이언트 만들기 → 유형 **웹 애플리케이션** →
     - 승인된 JavaScript 원본: `https://my-universe.vercel.app` (+ 로컬 시험용 `http://localhost:3000`)
     - 승인된 리디렉션 URI: `https://<ref>.supabase.co/auth/v1/callback`
     - 만들기 → 클라이언트 ID · 클라이언트 보안 비밀이 나온다(창을 닫기 전에 4로).
  4. Supabase 대시보드 → Authentication → Sign In / Providers → **Google** → Enable → Client ID · Client Secret 붙여 넣기 → Save.
  5. Authentication → URL Configuration:
     - Site URL: `https://my-universe.vercel.app`
     - Redirect URLs: `https://my-universe.vercel.app/**` , `http://localhost:3000/**`

## ④ Chroma Cloud

- 무슨 일: 생각 벡터(지난 생각 고르기)를 담을 저장소를 만든다.
- 왜: 벡터 저장은 ChromaDB 하나(WS0 결정 3). 로컬 · Docker는 컨테이너, 배포는 Chroma Cloud. Starter $0 + 사용량, 무료 크레딧 $5.
- 할 일:
  1. https://www.trychroma.com → Sign up(구글 계정 가능).
  2. Create database → 이름 `my-universe` (지역은 기본 AWS us-east-1).
  3. 그 데이터베이스의 Settings/Connect 화면에서 **API key 만들기** → 키(`CHROMA_API_KEY`), **Tenant ID**(`CHROMA_TENANT`), 데이터베이스 이름(`CHROMA_DATABASE` = `my-universe`).
  4. Billing에서 사용량 알림이 있으면 켠다.

## ⑤ Vercel 두 프로젝트

- 무슨 일: 같은 저장소를 두 번 가져온다. 백엔드(FastAPI, 저장소 루트)와 화면(Next.js, `infra/frontend`).
- 왜: 화면이 백엔드를 절대 주소로 부르는 구조라 코드 변경이 없고, 한 프로젝트로 묶는 Services는 아직 Beta다(README §1).
- 먼저 암호화 키 만들기(결과는 Vercel `DIARY_ENC_KEY` 칸에만 붙여 넣고 어디에도 저장하지 않기):

```bash
python3 -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

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
| `SUPABASE_ANON_KEY` | ② anon public 키 |
| `DATABASE_URL` | ② Transaction pooler URI |
| `DIARY_ENC_KEY` | 위 명령 결과(로컬 `.env.local` 것과 다른 새 키. 잃거나 바꾸면 저장된 일기를 못 연다) |
| `CHROMA_API_KEY` · `CHROMA_TENANT` · `CHROMA_DATABASE` | ④ |
| `FRONTEND_ORIGIN` | `https://my-universe.vercel.app` |
| `DAILY_ENTRY_LIMIT` | 사용자별 하루 일기 수. 넣지 않으면 `10` |
| `MONTHLY_COST_CAP_USD` | 사용자별 이달 추정 비용 상한(달러). 넣지 않으면 `5` |
| `ALLOWED_EMAILS` | **동규 · 현호 이메일**(구글 계정, 쉼표로: `a@gmail.com,b@gmail.com`). 목록 밖 계정은 "초대된 사람만 쓸 수 있어요"(403). 비우면 로그인한 누구나 쓸 수 있으니 꼭 넣는다 |
| `SUPABASE_SERVICE_ROLE_KEY` | ② service_role 키(계정 지우기 전용. 없으면 설정 화면의 "계정과 모든 기록 지우기"가 503) |
| `RESUME_LIMIT` | 기록 하나당 '이어서 하기' 횟수. 넣지 않으면 `3` |

넣지 않는 것: `LOG_TO_FILE`(기본 `0` = 표준 출력 → Vercel Logs), `CHROMA_HOST` · `CHROMA_PORT`(`CHROMA_API_KEY`가 있으면 Chroma Cloud를 씀), `RECORD_CONFIG_ID` · `OBSERVE_CONFIG_ID`(1차 Streamlit용), `API_DOCS`(없으면 `/docs` · `/openapi.json`이 꺼짐 — 배포는 끈 채로), `DEV_TEST_PASSWORD`(로컬 시험 전용).

4. Deploy → 빌드 로그에서 Python 함수가 `main.py`로 잡혔는지 본다(①의 `entrypoint = "main:app"`. `vercel.json`의 함수 키도 `main.py`라 다르게 잡히면 빌드가 실패해 드러난다).
5. 확인: `curl https://my-universe-api.vercel.app/health` → `{"status":"ok","version":"0.8.0"}`. `curl -s -o /dev/null -w "%{http_code}\n" https://my-universe-api.vercel.app/docs` → `404`(문서 꺼짐).
6. Settings → Functions에서 Region이 Seoul(icn1)인지 확인(`vercel.json`의 `regions`).

### 5-2. 화면 `my-universe`

1. https://vercel.com/new → 같은 저장소 다시 Import → Project Name `my-universe`.
2. **Root Directory: `infra/frontend`** → Framework Preset: Next.js(자동).
3. Environment Variables:

| 이름 | 값 |
| --- | --- |
| `NEXT_PUBLIC_API_BASE` | `https://my-universe-api.vercel.app` |
| `NEXT_PUBLIC_SUPABASE_URL` | ② Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ② anon public 키 |
| `NEXT_PUBLIC_DEV_LOGIN` | `0` |
| `NEXT_PUBLIC_MOCK` | `0` |

4. Deploy → `https://my-universe.vercel.app` 열기 → 구글 로그인 버튼 → 로그인 → 첫 화면.
5. 실제 주소가 `my-universe.vercel.app`과 다르면: 백엔드 `FRONTEND_ORIGIN`, ③-3 JavaScript 원본, ③-5 Site URL · Redirect URLs를 실제 주소로 고치고 백엔드를 Redeploy(Deployments → 최신 → ⋯ → Redeploy).
6. (선택) Settings → Functions → Region → Seoul(icn1).

### 5-3. 오류 알림 켜기

GitHub 저장소 → Settings → Secrets and variables → Actions → Variables 탭 → `API_URL` = `https://my-universe-api.vercel.app`, `WEB_URL` = `https://my-universe.vercel.app`. Actions 탭 → health → Run workflow로 한 번 돌려 초록인지 본다. 이후 매일 09:00에 확인하고 실패하면 메일이 온다.

## ⑥ 리허설(동규 하루 써 보기)

글은 가상 인물 글이나 Studio로 보내도 괜찮은 글로 쓴다. 휴대폰 · PC 둘 다.

- [ ] 구글 로그인 → 첫 화면 → 마음 날씨 질문이 첫 만남에만 나온다.
- [ ] 일기 쓰기 → 진행 단계가 하나씩 바뀐다(SSE) → 약 1분 뒤 결과 카드(생각 · 한마디 · 다음 질문).
- [ ] 쓰는 중에 비행기 모드 → 다시 켜기 → "이어서 하기"로 끝까지 간다.
- [ ] 우주: 해 · 작은 별 · 행성이 보이고, 행성을 누르면 영역을 넘는 선이 보인다.
- [ ] 버튼: 맞아요/아니에요, 좋아요/별로, 지켰어요/그만둘래요, 불편한 점 한 줄, 오늘은 살살 → 다시 열어도 반영돼 있다.
- [ ] 사람 목록: 일기에 나온 이름이 자동 등록, 지우기 하면 글에서 관계 말로 바뀐다.
- [ ] 말투 바꾸기(팩폭은 경고 확인 뒤에만).
- [ ] 위기 문장(예: 가상 문장 "다 끝내고 싶다")을 쓰면 평소 결과 대신 돌봄 화면 + 109 · 마들랜 안내.
- [ ] 일기 지우기 → 우주에서도 사라진다.
- [ ] Vercel → `my-universe-api` → Logs: 일기 글 · 인용 · 이름이 **한 줄도 안 보인다**. 오류(빨간 줄)가 있으면 오류 코드를 적어 둔다(보관 1시간).
- [ ] 다음 날: Upstage 콘솔 사용량 · `/stats`의 이달 추정 비용이 예상(글당 약 $0.08)과 맞는다. Chroma Cloud 사용량도 본다.

## ⑦ 현호 초대

- 무슨 일: 현호가 10/17부터 실제로 쓰게 한다.
- 왜: 동의 화면이 "테스트"라 등록한 사람만 로그인된다.
- 할 일:
  1. 현호 이메일(구글 계정)을 ③-2 테스트 사용자와 백엔드 `ALLOWED_EMAILS`(⑤-1)에 넣었는지 확인(없으면 추가 → 백엔드 Redeploy).
  2. 현호에게 보내기: 주소 `https://my-universe.vercel.app`, 휴대폰은 브라우저 메뉴의 "홈 화면에 추가", 구글 로그인 때 "Google에서 확인하지 않은 앱" 경고가 나오면 "계속"(테스트 상태라 나오는 경고), 일기에 쓴 사람 이름은 외부 AI로 보낼 때 가명으로 바뀐다는 것, 불편한 점은 결과 카드의 "불편한 점 한 줄"로.
  3. 10/16 기술 설명 문서(WS10)와 같이 보낸다.
