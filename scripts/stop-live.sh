#!/usr/bin/env bash
# 볼륨은 --volumes 를 준 경우에만 삭제한다. 이 개발 PC에서는 실행하지 않았다.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "${1:-}" == "--volumes" ]]; then
  echo "요청한 --volumes 로 볼륨을 삭제합니다."
  docker compose -f "$ROOT/infra/docker-compose.yml" down -v
else
  docker compose -f "$ROOT/infra/docker-compose.yml" down
  echo "스택을 내렸습니다. 볼륨은 유지했습니다."
fi
