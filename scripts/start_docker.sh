#!/usr/bin/env bash
# Docker 로 3개 켜기: ChromaDB 8000 · 백엔드 8001 · 화면 8002 (docker-compose.yml)
#   scripts/start_docker.sh          끄기: scripts/stop_docker.sh
# 포트를 바꾸려면: BACKEND_HOST_PORT=18001 FRONTEND_HOST_PORT=18002 CHROMA_HOST_PORT=18000 scripts/start_docker.sh
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo ".env 가 없습니다: cp .env.example .env 후 값 채우기"; exit 1; }
mkdir -p logs

docker compose up -d --build

B="http://localhost:${BACKEND_HOST_PORT:-8001}"
for _ in $(seq 1 30); do curl -sf "$B/health" >/dev/null && break; sleep 1; done
curl -sf "$B/health" >/dev/null && echo "백엔드 OK  $B/health" || echo "백엔드가 아직 응답하지 않음: docker compose logs backend"
echo "화면       http://localhost:${FRONTEND_HOST_PORT:-8002}"
echo "ChromaDB   http://localhost:${CHROMA_HOST_PORT:-8000}/api/v2/heartbeat"
