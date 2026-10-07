#!/usr/bin/env bash
# 로컬 전체 끄기: 백엔드(8001) · ChromaDB 컨테이너 · 로컬 Supabase. 데이터(도커 볼륨)는 남긴다.
#   scripts/dev_down.sh          # 끄기만
set -euo pipefail
cd "$(dirname "$0")/.."
pkill -f "uvicorn main:app --port 8001" 2>/dev/null && echo "백엔드 끔" || true
docker stop my-universe-chroma >/dev/null 2>&1 && echo "ChromaDB 끔" || true
supabase stop >/dev/null 2>&1 && echo "로컬 Supabase 끔(데이터는 남김)" || true
