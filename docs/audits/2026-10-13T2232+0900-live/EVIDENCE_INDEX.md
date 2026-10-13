# 증거 색인

| 주제 | 종류 | 위치 |
| --- | --- | --- |
| Compose 격리 | 실행 | `scripts/check-isolated-compose.ps1` 통과. 호스트 포트 55432, 18080 |
| 이미지 빌드 | 실행 | `maidops-isolated-backend`, `maidops-isolated-worker`, `maidops-isolated-trainer` |
| PostgreSQL 16.15 | 실행 | 격리 컨테이너 `SELECT current_setting('server_version')` |
| 빈 DB V1–V8 | 실행 | `maidops_live_audit.flyway_schema_history` 8행 |
| V6 후 기동 거부 | 실행 | `maidops-isolated-flyway-v6` 로그. missing column `log_storage_incomplete` |
| V6→V8 | 실행 | `maidops-isolated-flyway-latest` 로그. version 6에서 7, 8 |
| fixture 보존 | 실행 | `case-upgrade-audit` SHA-256과 `res-upgrade-audit` |
| 작업 왕복 | 실행 | `infra/isolated/live_audit_results.json` |
| 추가 확인 | 실행 | `infra/isolated/live_audit_followup.json`, trim 재시도 출력 |
| 모델 파일 | 실행 | 볼륨 안 `/models/mv-00000001.pt`, `.meta.json` |
| checksum 일치 | 실행 | DB `b33e0c05ff218464e5e0c48db303d55285b3494209849f3d2a75b13a88939694` = 파일 = meta |
| 평가 지문 | 실행 | DB metrics와 meta `07055a632a7ca3d019d7a2265f0010fb083a8a17bcacabf7db70edd64d66a2ed` |
| headless TUI | 실행 | `tui/.venv`가 18080에서 프로젝트·작업 조회 |
| 화면 | 없음 | 사람 눈 확인 없음 |
| 감독 실패 LIVE | 없음 | 주입하지 않음 |
| 기존 5432/8080 | 실행 | 검증 중 그 포트를 연 컨테이너를 만들지 않음. 종료 후 `docker ps`에 격리 컨테이너만 중지 상태로 남음 |

JSON 결과 파일은 스크립트가 중간에 기록한 상태다. 최종 판정은 `TEST_RESULTS.md`가 우선한다. 예를 들어 재시작 직후 폴링은 `PENDING`이었고, 이후 DB 행은 `MODEL`/`READY`다.
