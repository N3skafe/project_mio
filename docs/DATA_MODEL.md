# 데이터 모델

DEMO는 메모리 모델을 쓰고, LIVE는 같은 이름의 PostgreSQL 테이블을 씁니다. 마이그레이션은 `V1__init.sql`, `V2__worker_queue.sql`, `V3__rule_draft.sql`, `V4__training.sql`입니다.

| 이름 | PHASE 1 | 이후 |
| --- | --- | --- |
| Project | DEMO fixture. LIVE는 Flyway 시드 | 등록 프로젝트 |
| RegisteredTask | DEMO fixture. LIVE는 `plan_text`와, 신뢰 샘플은 `argv_json` | 워커는 argv가 있는 작업만 claim. `lab-*`는 문장이 다른 실패 50개 |
| Job | DEMO는 메모리. LIVE는 `jobs` 테이블. 생성 상태는 QUEUED | 워커가 상태를 진행 |
| OutputLine | DEMO 메모리. LIVE는 `job_events.sequence_no` | 로그 청크 |
| ErrorCase | 실패 로그에서 생성. 예측 초안과 확정 라벨을 분리 | `rule_version`, `matched_keyword` |
| LabelRevision | 사례 안의 목록. LIVE는 `label_revisions` | 변경 이력 |
| ResolutionRecord | DEMO fixture와 세션. LIVE는 `resolution_records` | 검색 대상 |
| TrainingRun | `training_runs`. 상태, fingerprint, 설정, 평가, 임대 | 조건 미달이면 행을 만들지 않음 |
| ModelVersion | `model_versions`. 체크섬, 장치, 지표, `is_default` | 사용자가 기본 모델을 고를 때만 참 |
| TrainingExample | `training_examples` | 실행에 묶인 확정 사례와 분할 |
| SplitAnchor | `dataset_split_anchors` | 한 번 정한 템플릿의 분할 |

## 라벨

```text
DB_CONNECTION
AUTH_PERMISSION
EXTERNAL_NETWORK
INPUT_VALIDATION
OTHER
```

기본 모델이 없으면 실패 로그의 예측 초안은 `draft_label`이고 `draft_source`는 `RULE_BASED`다. 기본 모델이 있으면 `draft_inferences`에 맡기고, 라벨이 오기 전에는 `inference_state=PENDING`이다. 학습기가 라벨을 반환하면 `draft_source`는 `MODEL`이다. `rule_version`은 `rules-1`이고 `matched_keyword`는 먼저 맞은 키워드다. 키워드가 없으면 라벨은 `OTHER`이고 `matched_keyword`는 null이다. 이 값은 정답 확률이 아니다.

`confirmed_label`은 응답에서만 계산한다. `review_status`가 `APPROVED` 또는 `REVISED`일 때 `current_label`과 같고, `DRAFT`와 `DEFERRED`에서는 null이다. 예측 초안은 검토 후에도 `draft_label`에 남는다.

시드 해결 기록의 `origin`은 `FIXTURE`다. `MODEL`은 enum에만 있고 값을 만들지 않는다.

우선순위는 `401`/`403`, `AUTH_PERMISSION`, `DB_CONNECTION`, `INPUT_VALIDATION`, `EXTERNAL_NETWORK`, 그다음 `OTHER`다. Java `FailureRuleClassifier`와 TUI `rules.py`가 같은 목록을 쓴다.

검토 상태:

```text
DRAFT -> APPROVED
DRAFT -> REVISED
DRAFT -> DEFERRED
```

승인 또는 수정된 사례만 확정 건수와 `GET /api/v1/error-cases/confirmed`에 들어간다. 보류는 제외된다. 변경 이력은 `label_revisions`다. 초안 행의 `source`는 `RULE_BASED`이고, 승인·수정·보류 행의 `source`는 `USER`다.

## 출력 한도

서버가 보관하는 이벤트 줄 수를 넘으면 앞부분을 버리고 첫 줄에 `[출력 잘림]`을 넣는다. 순서 번호는 폐기된 줄을 재사용하지 않는다. 이 표시는 로그 보관만 줄인 것이고, 종료 코드 0인 작업을 실패로 바꾸지 않는다.

워커의 출력 바이트 한도는 프로세스를 중단하는 다른 정책이다. 그때 `jobs.termination_reason`은 `OUTPUT_LIMIT_EXCEEDED`이고 상태는 `FAILED`다. `exit_code`가 0이어도 성공으로 저장하지 않는다. 로그 문장은 `OUTPUT_LIMIT_EXCEEDED`로 시작하고, `[출력 잘림]` 보관 문구와 구분한다.

실행 중 로그는 `job_event_batches`의 `(job_id, batch_id)`로 한 번만 저장한다. 같은 키의 다른 본문은 거절한다. `jobs.log_storage_incomplete`는 서버가 확인하지 못한 배치가 있다는 뜻이고, 프로세스 성공 여부와 별개다.

## 검색

검색은 대소문자를 무시한 부분 일치다. 작업 id와 출력, 오류 원문, 해결 기록의 원인과 방법을 본다. 임베딩 검색은 없다.

## 학습

학습 대상은 `review_status`가 `APPROVED` 또는 `REVISED`인 사례다. `DRAFT`와 `DEFERRED`는 빠진다.

조건은 확정 20건 이상, 서로 다른 라벨 2종 이상, 학습 8건·검증 4건·테스트 4건 이상, 각 분할의 라벨 2종 이상이다. 하나라도 부족하면 `POST /api/v1/training-runs`는 409이고 행과 점수를 만들지 않는다.

`split-1`은 로그를 소문자로 바꾸고 UUID, 경로, 긴 16진수, 숫자를 자리표시자로 바꾼 뒤 SHA-256 템플릿으로 묶는다. 같은 `job_id`이거나 같은 템플릿이면 한 그룹이다. 그룹 키는 템플릿 해시 목록의 SHA-256이다. 앵커가 없으면 그룹의 첫 라벨 이름으로 나눈 뒤 그룹 키 순서로 5칸 중 0은 TEST, 1은 VAL, 나머지는 TRAIN이다. 앵커가 있으면 그 템플릿의 분할을 따르고, TEST가 VAL과 TRAIN보다 우선한다. 처음 보는 그룹은 TRAIN이다. 앵커는 학습 실행을 만든 트랜잭션에서 저장된다. 이미 TEST인 템플릿은 이후 TRAIN으로 옮기지 않는다.

문장 벡터 식별자는 `hashing-char-ngram-v1`이다. 문자 3–5그램을 256차원에 해시하고 L2 정규화한다. 파라미터를 학습하지 않고 파일을 받지 않는다. MLP는 256에서 64, ReLU, dropout 0, 5클래스다. 새 학습 파일 형식은 `maidops-mlp-v2`이고, 이전 추론용 파일은 `maidops-mlp-v1`이다. 파일 이름은 `mv-00000001.pt` 형태다. 서버는 바이트 체크섬과 크기, symlink 여부만 보고 PyTorch로 열지 않는다. 가중치 검증과 재로드 평가는 Python 학습기가 한다.

`training_runs.status`는 `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`다. 진행 중인 실행은 하나다. 임대가 끊기면 `FAILED`이고 다시 큐에 넣지 않는다. `model_versions.is_default`는 학습 완료 때 거짓이고, `POST /model-versions/{id}/select-default` 뒤에만 참이다. 기본 모델은 하나다.

데이터 fingerprint는 사례 id, 라벨, 분할, 그룹 키, 원문 SHA-256을 이어 붙인 값의 SHA-256이다. 새 평가 JSON에는 정책 `supported-class-macro-f1-v2`, macro에 포함된 클래스, 평가 표본 수, 라벨 순서, 테스트 분할 지문, `checkpoint_evaluated`가 함께 들어간다. 행은 실제 라벨, 열은 예측 라벨이다. support는 행 합이고 predicted_count는 열 합이다. support가 0보다 크면 macro에 넣고, 예측이 없으면 precision·recall·F1은 0이다. support가 0이면 macro에서 뺀다. 그때 예측이 있으면 precision은 0이고 recall과 F1은 null이며 FP와 predicted_count는 남긴다. 실제 표본이 없거나 표본 있는 클래스가 2개 미만이면 점수를 만들지 않는다. 정책 필드가 없는 과거 기록은 legacy이며 이 평균과 같은 의미로 비교하지 않는다. 기존 행의 점수와 `is_default`는 자동으로 바꾸지 않는다.
