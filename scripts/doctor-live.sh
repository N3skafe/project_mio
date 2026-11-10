#!/usr/bin/env bash
# 점검만 한다. 프로세스를 종료하지 않는다. 이 개발 PC에서는 실행하지 않았다.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "MaidOps Lab LIVE 점검: $ROOT"
if command -v docker >/dev/null 2>&1; then
  echo "[통과] docker 명령"
  docker compose version
  docker info --format '{{.ServerVersion}}'
else
  echo "[실패] docker 명령이 없습니다."
fi
if command -v python3.11 >/dev/null 2>&1; then
  echo "[통과] python3.11"
else
  echo "[안내] python3.11 이 PATH에 없습니다."
fi
echo "health: curl -fsS http://127.0.0.1:8080/api/v1/health || true"
echo "프로세스는 종료하지 않았습니다."
