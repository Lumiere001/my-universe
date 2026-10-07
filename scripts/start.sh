#!/usr/bin/env bash
# 로컬 개발 한 번에 켜기: Supabase(로컬 스택) · ChromaDB(8000) · 백엔드(8001) · 화면(3000)
#   scripts/start.sh          끄기: scripts/stop.sh
# 키는 .env(백엔드) · infra/frontend/.env.local(화면)에서 코드가 읽는다. 이 스크립트는 값을 출력하지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs

[ -f .env ] || { echo ".env 가 없습니다: cp .env.example .env 후 값 채우기"; exit 1; }

# 1) Supabase 로컬 스택(supabase/config.toml 이 있을 때만). 이미 켜져 있으면 그대로.
if [ -f supabase/config.toml ]; then
  supabase status >/dev/null 2>&1 || supabase start >/dev/null
  echo "Supabase   http://127.0.0.1:54321 (Studio http://127.0.0.1:54323)"
fi

# 2) ChromaDB 컨테이너(이름 my-universe-chroma). 있으면 켜고, 없으면 만든다.
docker start my-universe-chroma >/dev/null 2>&1 \
  || docker run -d --name my-universe-chroma -p 8000:8000 -v my-universe-chroma:/data chromadb/chroma:1.5.9 >/dev/null
echo "ChromaDB   http://localhost:8000"

# 3) 백엔드(FastAPI). 출력은 logs/ (원문을 남기지 않는 것은 앱 규칙).
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-http://localhost:3000}" \
  nohup uv run --frozen uvicorn main:app --reload --port 8001 > logs/dev_backend.out 2>&1 &
echo "백엔드     http://localhost:8001/health"

# 4) 화면(Next.js 개발 서버)
[ -d infra/frontend/node_modules ] || npm --prefix infra/frontend install --silent
nohup npm --prefix infra/frontend run dev > logs/dev_frontend.out 2>&1 &
echo "화면       http://localhost:3000"
