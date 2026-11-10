#!/usr/bin/env bash
# Windows에서 우선 쓰는 스크립트의 Linux 대응. 이 개발 PC에서는 실행하지 않았다.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml")
if ! command -v docker >/dev/null 2>&1; then
  echo "docker 명령이 없습니다. 스택은 시작하지 않았습니다."
  exit 1
fi
echo "postgres, backend, worker, trainer 를 시작합니다."
"${COMPOSE[@]}" up --build -d
echo "준비 확인: curl -fsS http://127.0.0.1:8080/api/v1/health"
echo "TUI: MAIDOPS_MODE=LIVE MAIDOPS_BACKEND_URL=http://127.0.0.1:8080"
echo "샘플: /project list  다음  /project select trusted-sample  다음  /test"
