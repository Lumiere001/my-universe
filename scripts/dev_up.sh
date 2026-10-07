#!/usr/bin/env bash
# 로컬 전체 준비: 로컬 Supabase(Docker) + ChromaDB 컨테이너 + .env.local(백엔드 · 화면) + 시험용 계정 + 하늘 데모 우주.
# 키 · 비밀번호는 .env.local 에만 쓰고 화면에 내보내지 않는다. 여러 번 돌려도 된다.
#   scripts/dev_up.sh            # 준비만
#   scripts/dev_up.sh --serve    # 준비 + 백엔드(8001) 실행
set -euo pipefail
cd "$(dirname "$0")/.."

docker info >/dev/null 2>&1 || { echo "Docker 가 꺼져 있어요: open -a Docker 뒤 다시 실행"; exit 1; }
echo "1/5 로컬 Supabase"
supabase start >/dev/null 2>&1 || supabase start 2>&1 | grep -iv "key\|secret\|jwt" | tail -5
echo "2/5 ChromaDB(8000)"
docker start my-universe-chroma >/dev/null 2>&1 || docker run -d --name my-universe-chroma -p 127.0.0.1:8000:8000 -v my-universe-chroma:/data chromadb/chroma:1.5.9 >/dev/null
echo "3/5 .env.local"
uv sync --frozen -q
uv run --frozen python -m app.core.seed env
echo "4/5 시험용 계정"
uv run --frozen python -m app.core.seed accounts
echo "5/5 하늘 데모 우주(tester@)"
uv run --frozen python -m app.core.seed demo
echo "준비 끝. 백엔드: uv run --frozen uvicorn main:app --port 8001 · 화면: cd infra/frontend && npm run dev"
if [[ "${1:-}" == "--serve" ]]; then
  exec uv run --frozen uvicorn main:app --port 8001
fi
