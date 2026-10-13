# 실행 결과

API 기준 주소는 `http://127.0.0.1:18080`이다. DB는 격리 Postgres의 `maidops_live_audit`와 `maidops_upgrade_audit`이다.

## 데이터베이스

| 항목 | 상태 | 증거 |
| --- | --- | --- |
| PostgreSQL 버전 | PASS | `server_version` = 16.15 |
| 빈 DB `maidops_live_audit` | PASS | 생성 뒤 백엔드가 V1–V8을 적용 |
| schema history | PASS | 8행 모두 `success=true`, checksum 있음 |
| Flyway validate | PASS | 기동 로그 `Successfully validated 8 migrations` |
| JPA `ddl-auto: validate` | PASS | 최신 스키마에서 `Started MaidOpsApplication`. V6만 있는 DB에서는 `log_storage_incomplete` 누락으로 기동 실패 |
| 재기동 후 추가 migration 없음 | PASS | `Schema "public" is up to date. No migration necessary.` |
| V6까지 적용 | PASS | `SPRING_FLYWAY_TARGET=6`. history는 1–6 |
| V6 fixture 보존 | PASS | `case-upgrade-audit` raw SHA-256 `a523152b07345189224ab82a5517ddc745430864ea3ffe1915a5cefb20681bea`, `review_status=APPROVED`, 해결 기록 `upgrade cause token` |
| V7·V8 업그레이드 | PASS | `termination reason`, `event batches`. `termination_reason`은 null, `log_storage_incomplete=false` |

Flyway CLI는 따로 설치하지 않았다. 검증 경로는 격리 backend 이미지의 Spring Boot 3.5.16 Flyway다. 로그에 Community Edition 버전 문자열은 없었다.

## 작업과 검토

| 항목 | 상태 | 증거 |
| --- | --- | --- |
| 프로젝트·등록 작업 | PASS | `trusted-sample`과 기존 등록 작업. 감사 작업 5개는 격리 DB에만 INSERT |
| 성공 작업 | PASS | `job-00000004` `SUCCEEDED` `COMPLETED`. `RUNNING` 중 `check ok`가 이미 저장됨 |
| 실패와 오류 사례 | PASS | `job-00000005` `FAILED` `FAILED`, `case-00000003` |
| 승인 | PASS | `APPROVED` |
| 수정 | PASS | `case-00000004` 확정 라벨 `INPUT_VALIDATION`, revision `USER` |
| 보류 | PASS | `DEFERRED`. 확정 목록에 넣지 않음 |
| 해결 기록과 검색 | PASS | 원인 `감사 원인 토큰` 검색 hit 1 |
| 증분 로그 | PASS | `job-00000008`. `tick-0`만 있고 `tick-5`가 없을 때를 본 뒤, 종료 시 `tick-0`…`tick-5`와 `RESULT PASS` |
| 서버 보관 잘림 | PASS | `job-00000046` `SUCCEEDED` `COMPLETED`, `output_truncated=true`, `log_storage_incomplete=false`, 이벤트 500, 문구 `[출력 잘림] 최근 500줄만 표시합니다.` |
| 출력 한도 | PASS | `job-00000010` `FAILED` `OUTPUT_LIMIT_EXCEEDED` |
| 타임아웃 | PASS | `job-00000011` `FAILED` `TIMED_OUT` |
| 취소와 프로세스 트리 | PASS | 부모·자식·손자 cmdline을 본 뒤 `CANCELLED`. 이후 fixture 프로세스는 없음. 호스트 `tasklist`에는 없었다 |
| 병렬 idempotency | PASS | 응답은 둘 다 201. 행은 `live-parallel-key` → `job-00000013` 하나. 생성 메서드가 `201`로 고정되어 있다 |
| 프로세스 미종료 finish | PASS | `process_exited=false` 동안 `RUNNING`, `termination_reason` null |
| 배치 1회·재전송·충돌 | PASS | 204, 204, 409. DB의 `batch-alpha`는 1행 |
| 종료 후 새 배치 | PASS | 409. 저장본 재전송은 204 |
| 다른 worker | PASS | `audit-worker-2` 이벤트·heartbeat 409 |

`job-00000009`는 줄을 너무 빨리 찍어 워커 버퍼가 넘쳤다. `log_storage_incomplete=true`, 이벤트 207, `output_truncated=false`. 서버 보관 한도 검증으로는 쓰지 않는다.

## 학습과 추론

| 항목 | 상태 | 증거 |
| --- | --- | --- |
| 확정 25건 후 학습 조건 | PASS | `eligible=true` |
| CPU 학습 | PASS | `run-00000001` `SUCCEEDED`. 정책 `supported-class-macro-f1-v2`, `checkpoint_evaluated=true`, 완료 직후 `is_default=false` |
| 파일 | PASS | `/models/mv-00000001.pt` SHA-256 `b33e0c05ff218464e5e0c48db303d55285b3494209849f3d2a75b13a88939694`. DB·`.meta.json`의 `checkpoint_sha256`과 같음 |
| 메타데이터 | PASS | format `maidops-mlp-v2`, embedding `hashing-char-ngram-v1`, dim 256, 라벨 5개 순서 일치, metric policy 일치 |
| 평가 지문 | PASS | DB와 meta 모두 `07055a632a7ca3d019d7a2265f0010fb083a8a17bcacabf7db70edd64d66a2ed` |
| 기본 모델 선택 | PASS | `POST /model-versions/mv-00000001/select-default` 뒤 `is_default=true` |
| MODEL 초안 | PASS | `case-00000034` `draft_source=MODEL`, `inference_state=READY`, `model_version_id=mv-00000001` |
| 학습 lease | PASS | `run-00000002` `FAILED`. 메시지에 다시 학습하지 않는다는 문구. trainer를 다시 켠 뒤에도 `FAILED` |
| 작업 lease | PASS | `job-00000015` `FAILED`, 자동 재실행하지 않음 |
| 같은 worker의 늦은 요청 | PASS | heartbeat 409, 새 배치 409, finish 응답 200이어도 상태는 `FAILED` |
| 감독 실패 주입 | BLOCKED | 격리 워커의 상태 조회를 일부러 깨뜨리지 않았다 |

macro F1은 약 0.057이다. 이 값은 감사 fixture 25건으로 계산된 점수다.

추론이 연 checksum을 추론 행에 따로 남기지는 않는다. 확인한 연결은 모델 행 checksum, 볼륨 파일, meta, 그리고 `MODEL`/`READY`다. trainer는 checksum이 다르면 초안을 완료하지 않는다.

`code_version`은 `unknown`이다. 이미지 안 `MAIDOPS_CODE_ROOT=/opt/maidops`에 git 저장소가 없다.

## 재시작

| 항목 | 상태 | 증거 |
| --- | --- | --- |
| backend 재시작 | PASS | health 200, migration 추가 없음 |
| 재시작 후 추론 | PASS | `job-00000044`, `job-00000045`가 최종적으로 `MODEL` `READY` `mv-00000001`. 폴링이 끝난 시점에는 아직 `PENDING`이었다 |
| 컨테이너 재생성 | PASS | `up -d --force-recreate --no-deps`. 볼륨의 `mv-00000001.pt`와 `.meta.json` 유지 |
| 재생성 후 추론 | PASS | `MODEL` |

## TUI

| 항목 | 상태 | 증거 |
| --- | --- | --- |
| headless LIVE 조회 | PASS | `MAIDOPS_BACKEND_URL=http://127.0.0.1:18080`. 프로젝트 3, 작업 목록 45 |
| 화면을 사람이 확인 | BLOCKED | 터미널 UI를 눈으로 보지 않았다 |
