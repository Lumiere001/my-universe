#!/usr/bin/env bash
# scripts/start.sh 로 켠 것 끄기. 데이터(Supabase DB · Chroma 볼륨)는 지우지 않는다.
set -uo pipefail
cd "$(dirname "$0")/.."

# 백엔드(8001) · 화면(3000): 그 포트에서 듣는 프로세스를 끈다(--reload · next dev 의 하위 프로세스까지).
for port in 8001 3000; do
  pids=$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null)
  [ -n "$pids" ] && kill $pids && echo "포트 $port 끔"
done

docker stop my-universe-chroma >/dev/null 2>&1 && echo "ChromaDB 끔"
[ -f supabase/config.toml ] && supabase stop >/dev/null 2>&1 && echo "Supabase 끔(데이터는 남음)"
exit 0
