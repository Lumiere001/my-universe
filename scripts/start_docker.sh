#!/usr/bin/env bash
# Docker 로 3개 켜기: ChromaDB 8000 · 백엔드 8001 · 화면 8002 (docker-compose.yml)
#   scripts/start_docker.sh          끄기: scripts/stop_docker.sh
# 포트를 바꾸려면: BACKEND_HOST_PORT=18001 FRONTEND_HOST_PORT=18002 CHROMA_HOST_PORT=18000 scripts/start_docker.sh
#   (로컬 백엔드가 8001 을 쓰고 있으면 포트를 바꾸거나 먼저 끈다. my-universe-chroma(8000)는 아래에서 끈다)
# 따로 띄워 보기: COMPOSE_PROJECT_NAME=v8check 를 앞에 붙이고, 끌 때 docker compose -p v8check down -v --rmi local
# 로컬 Supabase(scripts/dev_up.sh)를 쓰면 .env.local 에서 컨테이너용 값(.env.docker.local)과 화면 빌드 값을 가져온다.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo ".env 가 없습니다: cp .env.example .env 후 값 채우기"; exit 1; }
mkdir -p logs

# 백엔드 컨테이너 → 로컬 Supabase 는 host.docker.internal 로. 이미 있으면 그대로 둔다(클라우드 값을 직접 넣은 경우).
if [ -f .env.local ] && [ ! -f .env.docker.local ]; then
  grep -E '^(SUPABASE_URL|SUPABASE_ANON_KEY|DATABASE_URL|DIARY_ENC_KEY)=' .env.local \
    | sed -E 's#(127\.0\.0\.1|localhost)#host.docker.internal#' > .env.docker.local
  echo ".env.docker.local 만듦(.env.local 의 Supabase · 암호화 값, 주소만 host.docker.internal)"
fi
# 화면 빌드 인자(NEXT_PUBLIC_*, 공개 값)는 infra/frontend/.env.local 에서. API 주소는 compose 가 BACKEND_HOST_PORT 로 정한다.
if [ -f infra/frontend/.env.local ]; then set -a; . infra/frontend/.env.local; set +a; fi

# 로컬 개발용 ChromaDB(my-universe-chroma)가 8000 을 잡고 있으면 끈다(데이터는 볼륨에 남음, scripts/start.sh 가 다시 켬)
if [ "${CHROMA_HOST_PORT:-8000}" = 8000 ] && docker stop my-universe-chroma >/dev/null 2>&1; then
  echo "my-universe-chroma 끔(8000 은 compose 의 ChromaDB 가 씀)"
fi

docker compose up -d --build

B="http://localhost:${BACKEND_HOST_PORT:-8001}"
for _ in $(seq 1 30); do curl -sf "$B/health" >/dev/null && break; sleep 1; done
curl -sf "$B/health" >/dev/null && echo "백엔드 OK  $B/health" || echo "백엔드가 아직 응답하지 않음: docker compose logs backend"
echo "화면       http://localhost:${FRONTEND_HOST_PORT:-8002}"
echo "ChromaDB   http://localhost:${CHROMA_HOST_PORT:-8000}/api/v2/heartbeat"
