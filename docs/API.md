# API

PHASE 2 HTTP API가 있습니다. JSON 필드는 snake_case이고 시각은 UTC입니다. 인증은 없습니다. 기본 바인딩은 `127.0.0.1`입니다.

## 공통

- 오류 본문은 `code`, `message`, `example`입니다.
- 목록은 `items`와 `next_cursor`입니다. `limit` 기본값은 50이고 1 이상 100 이하입니다.
- 작업 생성은 헤더 `Idempotency-Key`로 같은 본문의 재시도를 한 작업으로 모읍니다. 키 없이 호출하면 매번 새 작업입니다.
- 정수 진행률은 없습니다. QUEUED는 경과 시간만 계산할 수 있고, 실행 중이라는 뜻은 아닙니다.

## 경로

```text
GET  /api/v1/health
GET  /api/v1/projects
GET  /api/v1/projects/{id}
GET  /api/v1/projects/{id}/tasks
POST /api/v1/jobs
GET  /api/v1/jobs
GET  /api/v1/jobs/{id}
GET  /api/v1/jobs/{id}/events?after={sequence}
POST /api/v1/jobs/{id}/cancel
GET  /api/v1/error-cases
GET  /api/v1/error-cases/confirmed
GET  /api/v1/error-cases/{id}
POST /api/v1/error-cases/{id}/reviews
POST /api/v1/error-cases/{id}/resolutions
GET  /api/v1/resolutions
GET  /api/v1/resolutions?q={query}
GET  /api/v1/search?q={query}
GET  /api/v1/lab/status
POST /api/v1/training-runs
GET  /api/v1/training-runs
GET  /api/v1/training-runs/{id}
POST /api/v1/training-runs/{id}/cancel
GET  /api/v1/model-versions
POST /api/v1/model-versions/{id}/select-default
GET  /actuator/health
```

`/api/v1/health`는 `status`, `database`, `worker`, `authentication`을 반환합니다. 최근 20초 안에 워커 heartbeat가 있으면 `worker`는 `CONNECTED`이고, 없으면 `NOT_CONNECTED`입니다. 데이터베이스가 내려가면 HTTP 503입니다.

워커 전용 경로입니다. 사용자 명령 문자열이 아니라 서버에 등록된 argv만 claim 응답에 들어갑니다.

```text
POST /api/v1/worker/heartbeat
POST /api/v1/worker/claim
POST /api/v1/worker/jobs/{id}/heartbeat
POST /api/v1/worker/jobs/{id}/events
POST /api/v1/worker/jobs/{id}/finish
```

claim은 `FOR UPDATE SKIP LOCKED`로 `QUEUED` 작업 하나만 `RUNNING`으로 바꿉니다. 실행 중인 작업의 취소는 `CANCEL_REQUESTED`이고, 프로세스가 끝난 뒤의 finish만 `CANCELLED`로 확정합니다.

작업 생성 본문:

```json
{"project_id": "demo-api", "task_id": "api-db-check"}
```

응답 상태는 `QUEUED`이고 `started_at`은 null입니다.

## 작업 상태

```text
QUEUED -> CANCELLED
RUNNING -> CANCEL_REQUESTED -> CANCELLED
RUNNING -> SUCCEEDED
RUNNING -> FAILED
```

워커가 없으면 HTTP 취소는 QUEUED를 CANCELLED로 닫습니다. 워커가 claim하면 RUNNING이 되고, 실행 중 취소는 CANCEL_REQUESTED만 남깁니다. 프로세스 종료를 확인한 finish가 CANCELLED를 기록합니다. 종료된 행은 다른 결과가 덮어쓰지 못합니다.

## 오류 라벨

실패하면 오류 사례 하나를 저장합니다. `draft_label`, `draft_source`, `rule_version`, `matched_keyword`는 예측 초안입니다. 기본 모델이 없으면 `draft_source`는 `RULE_BASED`이고 `rule_version`은 `rules-1`입니다. 기본 모델이 있고 파일이 있으면 `inference_state`는 `PENDING`이고 라벨은 null입니다. 학습기가 argmax 라벨을 반환하면 `draft_source`는 `MODEL`입니다. 파일이나 응답이 없으면 규칙 초안으로 닫고 다시 추론하지 않습니다. 일치 키워드와 softmax는 정답 확률이 아니며 `score` 필드는 없습니다. `PENDING`인 사례는 승인, 수정, 보류가 거절됩니다.

`confirmed_label`은 `review_status`가 `APPROVED` 또는 `REVISED`일 때만 `current_label`과 같습니다. `DRAFT`와 `DEFERRED`는 `confirmed_label`이 null입니다. `GET /api/v1/error-cases/confirmed`는 승인·수정된 사례만 반환합니다.

`revisions`가 변경 이력입니다. 초안 행의 `source`는 `RULE_BASED`이고, 승인·수정·보류 행의 `source`는 `USER`입니다. 원인과 해결 방법은 승인 또는 수정 뒤에 저장합니다.

`GET /api/v1/search?q=`는 작업 로그, 오류 원문, 원인, 해결 방법을 키워드로 찾습니다. 일치가 없으면 `items`가 빈 배열입니다. 임베딩 검색과 외부 LLM은 없습니다.

## 학습

`GET /api/v1/lab/status`는 확정·초안·보류 건수, 클래스 분포, train/val/test 미리보기, 조건 이유, 진행 중인 실행, 기본 모델, 최신 모델, 모델 목록을 반환합니다. `download_required`는 거짓입니다. 조건이 부족해도 이 조회는 점수를 만들지 않습니다.

`POST /api/v1/training-runs`는 조건을 만족할 때만 `QUEUED` 행을 만들고 201을 반환합니다. 부족하면 409 `STATE`이고 행이 없습니다. 진행 중인 실행이 있으면 409입니다. 학습이 끝나도 `is_default`는 거짓입니다.

```text
QUEUED -> RUNNING -> SUCCEEDED
QUEUED -> FAILED
RUNNING -> FAILED
```

대기 취소는 즉시 `FAILED`입니다. 실행 중 취소는 `cancel_requested_at`만 남기고, 학습기가 파일을 지운 뒤 실패로 닫습니다. 임대가 끊긴 `RUNNING`은 `FAILED`이고 메시지에 자동으로 다시 학습하지 않는다고 적습니다. 다시 큐에 넣지 않습니다.

모델 비교는 `GET /api/v1/model-versions`와 상태 응답의 지표로 합니다. `POST /api/v1/model-versions/{id}/select-default`만 그 모델을 기본값으로 바꿉니다. 이전 기본값은 거짓이 됩니다.

학습기 전용 경로입니다. 헤더 `X-Trainer-Id`가 필요합니다.

```text
POST /api/v1/trainer/claim
GET  /api/v1/trainer/runs/{id}/examples
POST /api/v1/trainer/runs/{id}/heartbeat
POST /api/v1/trainer/runs/{id}/complete
POST /api/v1/trainer/runs/{id}/fail
POST /api/v1/trainer/inferences/claim
POST /api/v1/trainer/inferences/{id}/complete
POST /api/v1/trainer/inferences/{id}/fail
```

claim은 `FOR UPDATE SKIP LOCKED`로 `QUEUED` 하나만을 `RUNNING`으로 바꿉니다. 대기 실행이 없으면 204입니다. complete는 임베딩 식별자, 라벨 체계, 장치 `cpu` 또는 `cuda`, 시드, 설정, 5×5 혼동행렬을 받습니다. 서버가 행렬로 macro F1을 다시 계산하고, 제출 값과 1e-4보다 크게 다르면 거절합니다. 저장된 점수는 서버가 계산한 값입니다. 모델 파일은 `MAIDOPS_MODEL_DIR` 안의 `mv-`와 숫자 8자리 `.pt`만 읽고, 바이트 SHA-256이 본문과 같아야 합니다.

## 인증

localhost 단일 사용자이며 인증이 없습니다. 외부 서비스처럼 주소를 열지 않습니다. 팀 공유 때 인증과 프로젝트 권한을 추가합니다.
