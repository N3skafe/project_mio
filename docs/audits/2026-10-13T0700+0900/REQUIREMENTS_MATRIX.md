# 요구사항 추적

결과 값은 PASS, FAIL, BLOCKED, NOT_IMPLEMENTED, NOT_APPLICABLE 이다.
정적은 코드와 문서 대조이고, 실행은 이번 감사에서 명령을 돌린 결과다.

대상 commit: `ab1d66090e296f3a73aef14dad59130eae2cc34d`

## PHASE 1

| ID | 요구사항 | 구현 | 검증 | 결과 | 근거 |
| --- | --- | --- | --- | --- | --- |
| P1-01 | DEMO가 `tui/`만으로 실행되고 Java, DB, GPU, 외부 API를 요구하지 않음 | `DemoService`, `AppConfig` | 실행. TUI pytest는 JDK와 Docker 없이 종료 | PASS (실행) | `tui/` pytest. 네트워크 설치 없음 |
| P1-02 | Windows 실행 경로가 문서화됨 | `README.md`, `scripts/run-tui.ps1`, `scripts/test-tui.ps1` | 정적. 스크립트는 기존 `.venv`를 사용하고, 그 venv는 이 PC에서 동작 | PASS (정적, venv 존재 확인) | README 20–39행. 대화형 터미널 기동은 하지 않음 |
| P1-03 | Workspace, Review, Lab, History, 도움말, 조용한 모드, 명령 포커스 | `app.py`, `screens/` | 실행. 전체 스위트 두 번에서 앱 테스트 대부분이 통과. 스위트는 F-10으로 한 건씩 간헐 실패 | 기능 단언은 통과 회차 기준 PASS. 스위트 안정성은 FAIL | F-10 |
| P1-04 | 오류 명령이 앱을 종료하지 않음 | `parser.py`, `executor.py` | 실행. 잘못된 명령 테스트가 전체 실행의 실패 목록에 없음 | PASS (실행) | `tui/tests/test_app.py` |
| P1-05 | DEMO와 LIVE 표시. DEMO 학습과 점수를 실제 결과처럼 보이지 않음 | `display.py`, `demo_service.py`의 `lab_status` | 실행. 통과한 앱 테스트가 Lab 버튼 비활성과 학습 안내 문구를 확인 | PASS (headless). 목시 확인은 BLOCKED | `test_demo_failure_review_and_lab_stays_disabled` |
| P1-06 | 취소 후 늦은 완료가 PASS 또는 FAIL로 덮어쓰지 않음 | `DemoService` 토큰과 잠금 | 실행. 서비스 테스트는 실패 목록에 없음. 앱 `/cancel` 테스트는 1회 실패 후 8회 통과 | PASS (서비스). 앱 테스트는 F-10 | `demo_service.py` |
| P1-07 | 작업 상태가 섞이지 않고 새 세션이 이전 검토를 가지지 않음 | 작업 id 키, 새 `DemoService` | 실행. 해당 테스트가 실패 목록 밖에 있음 | PASS (실행) | `test_demo_service.py`, `test_fresh_app_does_not_reuse_previous_session` |
| P1-08 | 작업 중 UI 응답, 로그 스크롤, 갱신 시 포커스 유지 | `refresh_ui`. 매 갱신마다 작업 로그를 비우지 않음 | 정적과 일부 headless. 사람 눈의 스크롤은 미확인 | 정적 PASS. 목시 BLOCKED | `docs/UI_SPEC.md`, `app.py` |
| P1-09 | 작은 화면에서 핵심 기능 | 너비 100 미만 배치. 테스트 크기 78x24 | 실행 6회 중 4회 통과, 2회는 명령 대기 레이스 | F-10. 레이아웃 결함으로 단정하지 않음 | `test_narrow_layout_still_accepts_commands` |
| P1-10 | 한글과 ASCII를 사람이 확인 | UTF-8 안내, ASCII 아트 | 자동 문자열은 headless로 일부 확인. 터미널 글꼴은 보지 않음 | BLOCKED (목시) | `REPRODUCTION.md` 수동 목록 |

## PHASE 2

| ID | 요구사항 | 구현 | 검증 | 결과 | 근거 |
| --- | --- | --- | --- | --- | --- |
| P2-01 | API 경로, snake_case, UTC | Jackson SNAKE_CASE, JDBC timezone UTC | 정적과 통합 테스트 27개 통과 | PASS (실행, 내장 DB) | `ApiIntegrationTest` 16개 |
| P2-02 | 연결 실패가 작업을 만들지 않음 | TUI LIVE는 health 실패 시 DISCONNECTED | 기존 LIVE 테스트가 전체 TUI 실행의 실패 2건에 없음 | PASS (기존 테스트가 전체 실행에서 통과) | `tui/tests/test_api_service.py` |
| P2-03 | 빈 DB 마이그레이션과 재실행 | Flyway V1–V6 | 실행. 빈 내장 PG 14.10에 적용. 다음 컨텍스트는 버전 6, 변경 없음 | PASS (PG 14.10). PG 16 빈 DB는 BLOCKED | F-12 |
| P2-04 | health와 워커 표시 | `/api/v1/health` | 실행. 테스트는 heartbeat 전후를 확인. 기동 중 스택 GET은 CONNECTED | PASS (실행). 기동 중 스택은 읽기 1회 | surefire, health JSON |
| P2-05 | 작업 생성은 QUEUED. 성공으로 끝내는 사용자 HTTP가 없음 | `JobService.create`. 종료는 워커 finish | 실행. 해당 API 테스트 통과 | PASS (실행) | `ApiIntegrationTest` |
| P2-06 | Idempotency-Key | 전역 `key_text` PK, 해시 불일치 409, `FOR UPDATE` | 순차 테스트 통과. 병렬 동일 키는 미실행. 범위는 프로젝트별이 아니라 전역 | 순차 PASS (실행). 병렬 미실행 | `JobService.reserve` |
| P2-07 | 검증, 표준 오류, 페이지, 없는 ID, 프로젝트와 작업 불일치 | `code`, `message`, `example` | 실행. 입력 오류와 목록 페이지 테스트 통과 | PASS (실행) | `ApiIntegrationTest` |
| P2-08 | 검색어를 SQL이 아니라 데이터로 처리 | JPQL 파라미터와 LIKE escape | 정적 PASS. 따옴표 payload의 별도 실행은 없음 | 정적 PASS | `SearchService.likePattern` |
| P2-09 | 라벨 변경과 이력의 한 트랜잭션 | `@Transactional`에서 상태와 revision 저장 | 순차 저장은 테스트 통과. 개정 충돌은 없음 | 순차 PASS. 충돌 정책 NOT_IMPLEMENTED | F-07 |
| P2-10 | localhost, 인증 없음, 호스트 포트 비공개 | 기본 주소 `127.0.0.1`. Compose도 `127.0.0.1`. 컨테이너 수신은 `0.0.0.0` | 실행. 기동 중 포트가 `127.0.0.1`. health의 authentication은 NONE | PASS (호스트 바인딩). 인증은 문서대로 없음 | `docker-compose.yml`, Dockerfile |
| P2-11 | 프로젝트 간 권한 | 없음 | 단일 사용자 설계 | NOT_APPLICABLE | ROADMAP의 인증 미구현 |

## PHASE 3

| ID | 요구사항 | 구현 | 검증 | 결과 | 근거 |
| --- | --- | --- | --- | --- | --- |
| P3-01 | 등록 `{python}` argv만, `shell=False` | `RegisteredCommandResolver`, `resolve_command`, `runner.py` | 실행. 셸 연산자, `cmd.exe`, `..` 거부. fixture exit code 유지 | PASS (실행) | `test_worker.py`, 감사 테스트 |
| P3-02 | symlink로 루트 밖 스크립트 거부 | `resolve` 후 `is_relative_to` | 실행. 이 PC에서 symlink가 만들어졌고 `CommandRejected` | PASS (실행) | `test_symlink_script_outside_root_is_rejected` |
| P3-03 | 타임아웃과 출력 한도 | 작업 timeout 1–120초. 워커 루프는 한 번에 하나 | 한도 표시는 FAIL. 한 프로세스 루프는 정적 PASS | F-04 FAIL | `runner.py`, `loop.py` |
| P3-04 | 비밀 마스킹 | `mask_secrets` | 대입문과 Bearer는 통과. URI는 FAIL | F-03 FAIL | `masking.py` |
| P3-05 | 같은 작업의 이중 claim 방지 | `FOR UPDATE SKIP LOCKED` | 실행. 스레드 2개 테스트 통과 | PASS (실행, 내장 PG) | `onlyOneWorkerClaimsAQueuedCommand` |
| P3-06 | 임대 만료 후 덮어쓰기와 재큐 금지 | terminal finish는 반환. 만료는 FAILED | 실행. `expiredLeaseIsNotRequeued` 통과 | PASS (실행) | `WorkerJobService` |
| P3-07 | 상태 조회 실패 시에도 프로세스 종료 | 없음 | 실행으로 잔존 확인 | FAIL | F-01 |
| P3-08 | 취소 요청과 종료 확인의 분리 | RUNNING은 `process_exited` 뒤에만 CANCELLED | 실행. API 테스트와 Windows 손자 프로세스 테스트 통과 | PASS (실행) | `cancelRequestIsNotSuccessUntilTheProcessExits` |
| P3-09 | 결과 저장 전 워커 종료 | 출력을 메모리에 모았다가 마지막에 POST | 정적 FAIL. 사용자 워커는 종료하지 않음 | FAIL (정적) | F-08 |
| P3-10 | 로그 순서, 증분, 잘림 표시 | 서버 sequence와 500줄 문구 | 서버 표시는 정적 PASS. 워커 바이트 잘림은 표시되지 않음 | F-04 FAIL | `JobService.trim` |
| P3-11 | 실패마다 가짜 사례를 만들지 않음. 복수 오류 | 실패 1건당 사례 1건 | 제품 API가 1건으로 정의 | NOT_APPLICABLE (복수 추출). 1건 생성은 PASS | `API.md`, `recordFailure` |
| P3-12 | 사용자 스택의 재시작과 단절 | 컨테이너가 healthy | 중지와 변경을 하지 않음 | BLOCKED | 5432와 8080 |

## PHASE 4

| ID | 요구사항 | 구현 | 검증 | 결과 | 근거 |
| --- | --- | --- | --- | --- | --- |
| P4-01 | 다섯 라벨, 우선순위, 숫자 안 401/403 제외 | Java, TUI, trainer 규칙 | 실행. Java 2개, trainer, 감사 테스트 2개 통과 | PASS (실행) | `FailureRuleClassifierTest` |
| P4-02 | 초안 source와 규칙 버전. 자동 확정과 확률 점수 없음 | `confirmed_label`은 승인 또는 수정만 | 실행. 미검토 초안 테스트 통과. `score` 필드 없음 | PASS (실행) | `unreviewedRuleDraftIsNotAConfirmedLabel` |
| P4-03 | 기본 모델이면 MODEL, 응답이 없으면 RULE_BASED로 닫음 | `ModelDraftService` | 실행. API 상태 기계 통과. 제출 라벨은 테스트가 직접 넣음 | 상태 기계 PASS. 실측 argmax와 API 연결은 미실행 | `ModelDraftIntegrationTest` |
| P4-04 | 승인, 수정, 보류 | `ReviewDecision` | 순차 테스트 PASS. 개정 충돌은 없음 | 순차 PASS. F-07 NOT_IMPLEMENTED | `ErrorCaseService` |
| P4-05 | 미검토와 보류는 학습 제외. snapshot 라벨 고정 | `training_examples.label` 복사 | 실행. draft 행 0건 | 라벨 snapshot PASS | `TrainingLabIntegrationTest` |
| P4-06 | 키워드 검색 | `SearchService` | 빈 검색어, 없는 키워드, 한글 원인은 기존 테스트 통과 | 검색 PASS. 프로젝트 필터 NOT_APPLICABLE. 페이지는 F-11 | `SearchService` |
| P4-07 | 외부 LLM과 임베딩 검색이 없음 | 호출 코드 없음 | 정적. 이번 세션에서 해당 호출 없음 | PASS | `docs/ROADMAP.md` |

## PHASE 5

| ID | 요구사항 | 구현 | 검증 | 결과 | 근거 |
| --- | --- | --- | --- | --- | --- |
| P5-01 | 확정 라벨만 학습. 조건 미달이면 행과 점수 없음 | `TrainingPolicy` | 실행. 부족 데이터 테스트 통과 | PASS (실행) | `insufficientConfirmedDataDoesNotCreateAScore` |
| P5-02 | 같은 그룹은 한 분할. 기존 TEST는 TRAIN으로 내려가지 않음 | `DatasetSplitter`와 anchor | 실행. 분할 테스트 3개와 두 번째 학습의 TEST 유지 통과 | PASS (실행) | `DatasetSplitterTest` |
| P5-03 | 고정 해시 임베딩, 다운로드 없음 | `hashing-char-ngram-v1`, 256차원 | 실행. 동일 문자열 벡터 일치 | PASS (실행) | `test_hashing_embedding_is_stable_and_has_no_parameters` |
| P5-04 | CPU 학습. CUDA가 없으면 `cuda` 요청은 실패 | `device.py` | 실행. trainer 7개 통과. CUDA 실학습은 불가 | CPU 정책 PASS. CUDA BLOCKED | torch 2.14.1+cpu |
| P5-05 | 그룹이 두 분할이면 파일을 쓰지 않음 | `_assert_groups` | 실행 통과 | PASS (실행) | `test_mixed_group_does_not_write_a_score` |
| P5-06 | macro F1은 실제 예측으로 계산. 평가 불가면 가짜 점수 없음 | `from_confusion` | 지원 0의 null과 47/60은 PASS. 지원이 있고 예측이 0인 클래스 제외는 FAIL | F-02 FAIL | `metrics.py`, `ClassificationMetrics.java` |
| P5-07 | 학습 완료가 기본 모델을 바꾸지 않음 | `select-default`만 기본값 | 실행. 더미 파일 테스트가 플래그를 확인 | 플래그 PASS. 점수와 가중치 대응은 F-09 | `TrainingService.selectDefault` |
| P5-08 | `mv-` 파일 이름, 체크섬, 경로 이탈 거부 | `readModelFile` | 정적. 형식 다른 바이트도 체크섬이 맞으면 저장 | 경로 제한 PASS. 형식 검증은 F-09 | `TrainingService` |
| P5-09 | 선택한 기본 모델이 다음 실패 초안에 쓰임 | claim이 저장된 모델 파일을 반환 | API 상태 기계 PASS. 실제 MLP 왕복은 미실행 | 상태 기계 PASS. 가중치 왕복 BLOCKED | 사용자 DB 미사용 |
| P5-10 | 끊긴 학습과 추론을 다시 큐에 넣지 않음 | sweeper가 FAILED | 실행 통과 | PASS (실행) | 임대 만료 테스트 2개 |
| P5-11 | 소형 fixture 학습을 일반화 성능으로 말하지 않음 | 분리 가능한 토큰 | 실행 통과. 해석은 스모크 | PASS (스모크만) | `test_cpu_training_beats_the_rule_baseline_on_a_fixed_split` |

## 전체 LIVE

| ID | 요구사항 | 결과 | 근거 |
| --- | --- | --- | --- |
| L-01 | 프로젝트 생성부터 재시작 복원까지 | BLOCKED | 5432와 8080에 쓰지 않음. 격리 계획은 `SUMMARY.md` |
| L-02 | 기동 중 스택이 localhost에 있는지 | PASS (관찰) | `docker ps`, health GET 1회 |
| L-03 | API 통과를 TUI 통과로 세지 않음 | 이 표가 그 구분 | TUI는 F-10. API 27개와 TUI 59개는 별도 |
