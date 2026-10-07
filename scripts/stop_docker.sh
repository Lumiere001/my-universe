#!/usr/bin/env bash
# scripts/start_docker.sh 로 켠 3개 끄기. Chroma 볼륨은 남긴다(지우려면 docker compose down -v).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose down
