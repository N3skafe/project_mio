# 발견 사항

제품 코드는 수정하지 않았다. 실행으로 확인한 항목과 코드 경로로 확인한 항목을 구분한다.

## F-01

- 심각도: HIGH
- 제목: 작업 상태 조회 예외가 자식 프로세스를 남긴다
- 실제 결과: `run_registered_process` 루프 안에서 `should_cancel()`이 예외를 던지면 함수가 그대로 빠져나가고, 이미 시작한 프로세스는 살아 있다. 감사 테스트에서 PID 13504가 예외 이후에도 살아 있었다. 테스트 `finally`가 `taskkill /T /F`로 정리한 뒤 `tasklist`에는 남아 있지 않았다.
- 기대 결과: 상태 조회나 heartbeat가 실패해도 프로세스 트리를 끝내고, 타임아웃 감시가 끊긴 채 작업을 계속 실행하지 않는다.
- 영향: 백엔드가 재시작되거나 상태 GET이 실패하면 Windows에서 등록 스크립트가 남는다. 루프가 끝났으므로 `timeout_seconds`도 더 이상 적용되지 않는다. Docker에서 워커가 PID 1이면 컨테이너 종료와 함께 죽을 수 있으나, 그 정리는 이 함수가 하지 않는다.
- 코드 위치: `worker/src/maidops_worker/runner.py` 57–76행. `Popen` 뒤에 `try/finally`가 없다. `worker/src/maidops_worker/loop.py` 66–70행의 `job_status()`는 `raise_for_status()`라서 HTTP 오류가 이 경로로 들어온다. `run_loop`도 `_execute_claimed` 예외를 잡지 않는다.
- 재현: `REPRODUCTION.md`의 F-01. 감사 테스트 `audit-tests/test_worker_boundaries.py::test_status_poll_error_stops_the_child_and_enforces_timeout` 실패.
- 개선 방향: 루프를 `try/finally`로 감싸고, 예외·타임아웃·취소·잘림에서 `terminate_process_tree`를 호출한 뒤 종료를 확인한다. 워커 루프는 그 실패를 finish로 남기고 다음 작업을 계속한다.
- 관련 테스트: 기존 `worker/tests/test_worker.py::test_cancel_stops_the_slow_fixture_process_tree`는 정상 취소만 본다. 예외 경로는 없다.

정상 취소에서 손자 프로세스를 끝내는 경로는 감사 테스트 `test_cancel_kills_a_grandchild_process`가 통과했다. F-01은 그 경로가 예외로 건너뛰어질 때의 문제다.

## F-02

- 심각도: MEDIUM
- 제목: 지원이 있는 클래스를 한 번도 예측하지 않으면 macro F1에서 빠진다
- 실제 결과: INPUT 2건을 모두 EXTERNAL로 예측한 행렬에서 INPUT의 precision은 `None`, recall은 `0.0`, f1은 `None`, support는 2다. macro F1은 `1.0`이다. DB와 AUTH만 평균에 들어갔다.
- 기대 결과: 테스트에 존재하는 클래스의 F1은 0이고, macro F1은 `(1 + 1 + 0) / 3`이다.
- 영향: 한 클래스를 전혀 맞히지 않아도 제목의 macro F1이 1로 남을 수 있다. 클래스별 칸에는 null이 보이지만, 비교와 기본 모델 선택은 macro F1을 함께 보여 준다. 기존 Java 테스트 `macroF1UsesOnlyClassesThatHaveSupport`는 지원 0인 클래스만 검사해서 이 경우를 통과시킨다.
- 코드 위치: `trainer/src/maidops_trainer/metrics.py` 72–83행. 같은 조건이 `backend/src/main/java/lab/maidops/lab/ClassificationMetrics.java` 46–59행에 있다. 서버는 제출된 행렬로 이 식을 다시 계산한다.
- 재현: `REPRODUCTION.md`의 F-02. 감사 테스트 `test_supported_class_with_no_predictions_lowers_macro_f1` 실패.
- 개선 방향: support가 0일 때만 F1을 null로 둔다. support가 있고 예측이 0이면 precision 0, recall 0, F1 0으로 평균에 넣는다. Java와 Python을 같이 바꾸고, 이 행렬을 양쪽 테스트에 넣는다.
- 관련 테스트: 손계산 47/60 테스트는 지원 0과 일부 오분류만 확인한다. 이번 행렬은 그 테스트에 없다.

Python에서 실행했다. Java 식은 같은 소스 조건으로 정적 확인했다. JDK 21 백엔드 테스트 전체는 통과했지만 이 행렬을 포함하지 않는다.

## F-03

- 심각도: MEDIUM
- 제목: 접속 URI의 비밀번호가 로그 마스킹을 통과한다
- 실제 결과: `postgresql://app:supersecret@127.0.0.1:5432/maidops`를 `mask_secrets`에 넣으면 `supersecret`이 그대로다.
- 기대 결과: 비밀번호처럼 보이는 URI userinfo는 로그에 남기 전에 가린다. 이 문자열의 `supersecret`은 감사 픽스처이며 저장소 비밀이 아니다.
- 영향: DB 오류 한 줄에 접속 URI가 있으면 `job_events`와 오류 사례 원문에 비밀번호가 저장된다. 외부 전송 코드는 찾지 못했다. 노출 범위는 로컬 DB와 화면이다.
- 코드 위치: `worker/src/maidops_worker/masking.py` 7–15행. `password=` 형태와 `Bearer`만 치환한다.
- 재현: 감사 테스트 `test_uri_password_is_masked` 실패.
- 개선 방향: `scheme://user:password@host` 형태를 가린다. 기존 `token=` / `Bearer` 테스트는 유지한다.
- 관련 테스트: `test_masks_secret_assignments`는 대입문과 Bearer만 통과한다.

## F-04

- 심각도: MEDIUM
- 제목: 바이트 한도로 잘린 출력이 종료 코드 0의 성공 finish로 올라간다
- 실제 결과: 100자 줄을 두 번 출력하고 끝나는 스크립트, 한도 40바이트에서 finish 인자는 `exit_code=0`, `process_exited=True`, `timed_out=False`였다. `output_truncated` 키는 없다.
- 기대 결과: 한도를 넘기면 잘림이 finish와 이벤트에 표시되고, 잘린 실행을 조용한 성공으로 저장하지 않는다.
- 영향: 서버 `finish`는 종료 코드 0이면 `SUCCEEDED`다. 워커 한도로 버린 줄은 성공 로그에서 사라질 수 있다. 서버의 500줄 잘림 표시는 워커가 이미 버린 줄을 복구하지 못한다.
- 코드 위치: `worker/src/maidops_worker/runner.py` 104–118행이 한도 초과 줄을 버린다. `loop.py` 80–86행 finish는 `exit_code`, `process_exited`, `timed_out`만 보낸다. `WorkerJobService.finish`는 그 세 필드로 성공과 실패를 가른다.
- 재현: 감사 테스트 `test_byte_limit_is_visible_on_finish` 실패.
- 개선 방향: `ProcessResult.output_truncated`를 finish에 포함하고, 참이면 성공으로 닫지 않으며 첫 이벤트에 잘림을 남긴다.
- 관련 테스트: 기존 워커 테스트의 출력 한도는 8000바이트라서 이 경로를 타지 않는다.

## F-05

- 심각도: MEDIUM
- 제목: README·PROJECT·SECURITY가 구현과 다르다
- 실제 결과:
  - `README.md` 알려진 제한과 `docs/PROJECT.md`는 학습된 MLP가 새 실패 로그를 분류하지 않는다고 적는다.
  - `ModelDraftService.recordFailure`는 기본 모델과 파일이 있으면 `draft_source=MODEL`, `inference_state=PENDING`으로 저장한다. `docs/ROADMAP.md`, `docs/API.md`, TUI 도움말은 그 동작을 완료로 적는다.
  - `docs/SECURITY.md` PHASE 2는 `registered_tasks`에 argv 열이 없다고 적는다. `V2__worker_queue.sql`은 `argv_json`을 추가하고 샘플 명령을 넣는다.
  - README는 이 개발 PC에 Docker가 없다고 적는다. 감사 시점에는 Compose 스택 4개가 떠 있었다.
- 기대 결과: 동작 설명, 보안 경계, 환경 안내가 현재 코드와 같다.
- 영향: README만 보면 모델 초안이 없는 것으로 시연을 설명하게 된다. SECURITY만 보면 등록 명령 실행이 없는 것으로 본다.
- 코드 위치: `README.md` 157–161행, `docs/PROJECT.md` 9행, `docs/SECURITY.md` 6행, `docs/ROADMAP.md` 26행, `backend/src/main/java/lab/maidops/lab/ModelDraftService.java` 78–104행, `backend/src/main/resources/db/migration/V2__worker_queue.sql` 9행.
- 재현: 파일을 나란히 읽는다. 모델 초안 상태 전이는 `ModelDraftIntegrationTest`가 내장 DB에서 통과했다. 그 테스트는 실측 추론이 아니라 API에 라벨을 제출한다.
- 개선 방향: PROJECT와 README 제한 문장을 API·ROADMAP과 같게 고친다. SECURITY의 argv 문장을 등록 argv만 허용한다는 현재 경계로 바꾼다. Docker 문장은 확인한 환경과 확인하지 못한 환경을 구분한다.
- 관련 테스트: 없음. 문서 대조다.

## F-06

- 심각도: MEDIUM
- 제목: 문서의 백엔드 테스트 명령이 이 PC의 JDK를 고르지 못한다
- 실제 결과: `scripts/test-backend.ps1`은 `C:\Program Files\Java\jdk-21`이 있을 때만 `JAVA_HOME`을 바꾼다. 그 경로는 없다. 사용자 `JAVA_HOME`은 JDK 11이다. `pom.xml`의 `java.version`은 21이다.
- 기대 결과: 저장소 스크립트가 이 PC에 있는 JDK 21로 테스트를 실행한다.
- 영향: README와 스크립트만 따라가면 JDK 11로 Maven이 돈다. 이번 감사의 녹색 백엔드 결과는 그 스크립트가 아니라 `JAVA_HOME=C:\Program Files\Java\jdk-21.0.12.1`와 `mvnw -o test`로 얻은 것이다.
- 코드 위치: `scripts/test-backend.ps1` 3–7행, `README.md` 78–81행.
- 재현: `Test-Path 'C:\Program Files\Java\jdk-21'`는 거짓이다. `Test-Path 'C:\Program Files\Java\jdk-21.0.12.1'`는 참이다. JDK 11로 컴파일 실패 문구는 일부러 실행하지 않았다.
- 개선 방향: 스크립트가 `jdk-21*`를 찾거나, 실패 시 JDK 11로는 진행하지 않고 경로를 오류로 보여 준다.
- 관련 테스트: 백엔드 27개는 올바른 JDK 21로 통과.

## F-07

- 심각도: MEDIUM
- 제목: 라벨 검토에 개정 기준이 없어 마지막 쓰기가 이긴다
- 실제 결과: `ErrorCaseService.review`는 사례를 id로 읽고 상태를 덮어쓴다. 기대 revision, `If-Match`, 행 잠금이 없다.
- 기대 결과: 병렬 수정은 이전 revision을 기준으로 한쪽이 거절되거나, 그 정책이 문서에 있다.
- 영향: 같은 사례를 두 요청이 승인·수정하면 나중 커밋만 남고, 이력에는 두 USER 행이 순서대로 쌓일 수 있다. 단일 사용자 화면의 순차 클릭은 이 창이 짧다.
- 코드 위치: `backend/src/main/java/lab/maidops/errorcase/ErrorCaseService.java` 70–80행, 107–131행.
- 재현: 이번 감사에서 병렬 HTTP는 사용자 DB를 피하기 위해 실행하지 않았다. 정적 경로로 확인했다. 재현 절차는 `REPRODUCTION.md`.
- 개선 방향: 검토 요청에 마지막 revision id를 받고, 다르면 409를 반환한다. 갱신은 `SELECT … FOR UPDATE`와 함께 한다.
- 관련 테스트: 기존 테스트는 순차 승인·수정·보류만 통과한다.

## F-08

- 심각도: MEDIUM
- 제목: 프로세스 출력이 종료 후에 한 번에 전송된다
- 실제 결과: 워커는 `run_registered_process`가 끝난 다음 `append_events`와 `finish`를 호출한다. 실행 중 증분 이벤트는 없다.
- 기대 결과: 실행 완료 후 저장 전에 워커가 죽어도 이미 나온 출력이 남거나, 그 공백이 운영 한계로 문서화된다.
- 영향: 프로세스는 끝났는데 POST 전에 워커가 죽으면 출력은 워커 메모리에서 사라진다. 임대 만료 뒤 서버는 `FAILED`와 그때까지 DB에 있던 이벤트만으로 오류 사례를 만든다. 성공으로 바꾸거나 다시 큐에 넣지는 않는다.
- 코드 위치: `worker/src/maidops_worker/loop.py` 72–86행. `WorkerJobService.failWithoutRerun`은 이미 저장된 이벤트로 원문을 만든다.
- 재현: 사용자 워커를 죽이지 않았다. 코드 순서와 `REPRODUCTION.md`의 절차로 확인한다.
- 개선 방향: 줄을 읽는 동안 일정 크기마다 events를 저장한다. finish는 이미 저장된 로그 뒤에 상태만 닫는다.
- 관련 테스트: API 테스트는 테스트 코드가 events를 직접 넣은 뒤 finish를 호출한다. 워커 프로세스의 전송 시점은 보지 않는다.

## F-09

- 심각도: MEDIUM
- 제목: 서버는 점수와 맞는 행렬만 저장하고, 그 행렬이 가중치에서 나왔는지는 보지 않는다
- 실제 결과: `TrainingLabIntegrationTest`는 모델 경로에 `not-a-loaded-checkpoint`라는 텍스트를 쓰고, 미리 만든 혼동행렬로 complete를 호출해 `is_default=false`인 모델 행을 만든다. 서버는 파일 이름 패턴, 크기, SHA-256, 행렬과 점수의 내부 일치만 확인한다.
- 기대 결과: 저장된 macro F1은 그 파일의 예측으로 계산됐다는 검증과 구분된다. 체크포인트 형식이 아니면 모델 버전으로 남기지 않는 편이 평가 기록과 맞다.
- 영향: 인증 없는 trainer complete를 호출할 수 있는 로컬 프로세스는, 자기 모순이 없는 행렬과 임의 바이트만으로 화면에 점수를 만들 수 있다. 공식 학습기는 실제 `torch.save`를 한다. Java 통합 테스트의 녹색은 그 학습의 성능 증거가 아니다.
- 코드 위치: `backend/src/main/java/lab/maidops/lab/TrainingService.java` 551–568행. `backend/src/test/java/lab/maidops/TrainingLabIntegrationTest.java` 124행과 213–255행. 학습기 쪽 실제 예측은 `trainer/src/maidops_trainer/train.py`의 `evaluate`.
- 재현: 기존 `trainingDoesNotReplaceTheDefaultModel`가 내장 DB에서 통과한 것이 이 동작이다. 사용자 DB에서는 실행하지 않았다.
- 개선 방향: 서버가 PyTorch를 실행하지 않는 설계는 유지하되, 파일 앞부분의 `format`, `embedding_id`, `label_schema_version`이 `maidops-mlp-v1` / `hashing-char-ngram-v1` / `labels-1`이 아니면 complete를 거절한다. 테스트의 더미 파일과 실측 학습 테스트를 이름과 단언에서 나눈다.
- 관련 테스트: `trainer/tests/test_train.py` 7개는 CPU fixture에서 실제 학습·저장·로드·argmax를 통과했다. 그 점수를 일반화 성능으로 쓰지 않는다.

## F-10

- 심각도: LOW
- 제목: Textual 앱 테스트가 명령 처리 완료 전에 단언하는 경우가 있다
- 실제 결과: `test_narrow_layout_still_accepts_commands`는 격리 실행 6회 중 2회 실패했다. 실패 실행은 약 0.42초, 통과 실행은 약 0.52–0.57초였다. 실패 단언은 `/help` 이후 활동 로그에 `도움말`이 없는 것이다. 전체 TUI 스위트 두 번째 실행은 59개 중 이 테스트만 실패했다. 첫 전체 실행에서는 다른 테스트 `test_cancel_from_command_is_not_reported_as_pass`가 실패했고, 그 테스트만 8회 다시 돌렸을 때는 모두 통과했다.
- 기대 결과: 앱 상호작용 테스트는 명령 핸들러가 끝난 뒤에 상태를 읽는다.
- 영향: 간헐 실패가 화면 결함처럼 보인다. 78칸 레이아웃이 명령을 잃는다고 단정할 증거는 아니다. 통과한 4회는 같은 크기에서 도움말 문구와 비활성 학습 버튼을 확인했다.
- 코드 위치: `tui/tests/support.py` 30–35행이 `action_submit()` 뒤 `pilot.pause()`를 한 번 호출한다. Textual 8.2.8 `Input.action_submit`은 `Submitted` 메시지만 올린다. `Pilot.pause()`는 `wait_for_idle(0)`이라 최소 대기 시간이 0이다.
- 재현: `REPRODUCTION.md`의 F-10.
- 개선 방향: `submit`이 활동 로그나 서비스 상태가 바뀔 때까지 `wait_for`로 기다린다. 제품 위젯을 이 테스트 실패만으로 고치지 않는다.
- 관련 테스트: `tui/tests/test_app.py` 175–183행, 109–123행.

## F-11

- 심각도: LOW
- 제목: 검색이 limit 없이 일치 행을 모두 메모리에 담는다
- 실제 결과: `SearchService.search`는 작업, 이벤트, 오류 사례, 해결 기록을 각각 조회해 한 목록으로 만들고 `next_cursor`를 항상 null로 둔다. 컨트롤러에 `limit`이 없다.
- 기대 결과: 목록 API의 limit 1–100과 커서와 같거나, 검색만 예외라는 점이 API 문서에 있다.
- 영향: 로그가 많아지면 한 번의 검색이 큰 응답을 만든다. 빈 검색어는 400이다. SQL은 바인딩 파라미터와 `ESCAPE '\'`라서 검색어가 쿼리 문자로 실행되지는 않는다.
- 코드 위치: `backend/src/main/java/lab/maidops/search/SearchService.java` 36–56행. Repository의 `like concat('%', :query, '%')`.
- 재현: 정적 검토. 기존 `ApiIntegrationTest`는 짧은 키워드와 결과 없음만 통과했다. 이번 감사에서 대량 행을 넣지 않았다.
- 개선 방향: `limit`과 커서를 적용하거나 API 문서에 검색은 비페이지라고 적는다.
- 관련 테스트: `ApiIntegrationTest.reviewAndResolutionFollowTheStoredState`, `unreviewedRuleDraftIsNotAConfirmedLabel`.

## F-12

- 심각도: LOW
- 제목: 백엔드 자동 테스트의 PostgreSQL은 14.10이다
- 실제 결과: Zonky 내장 서버 로그는 `PostgreSQL 14.10`이었다. Compose 이미지는 `postgres:16-alpine`이다. Flyway V1–V6는 빈 14.10에서 적용되었고, 같은 JVM의 다음 Spring 컨텍스트는 버전 6에서 추가 변경 없이 통과했다.
- 기대 결과: 문서의 실행 데이터베이스와 테스트 데이터베이스의 메이저 버전이 같거나, 다르다는 사실이 테스트 계획에 있다.
- 영향: 14에서 통과한 SQL이 16에서 다르면 이번 27개 결과만으로 잡히지 않는다. `SKIP LOCKED`와 Flyway 자체는 14에서 동작했다. 이미 떠 있는 16 스택의 health는 UP이지만, 그 데이터베이스의 `flyway_schema_history`는 조회하지 않았다.
- 코드 위치: `backend/pom.xml`의 `embedded-postgres` 2.0.7. `infra/docker-compose.yml`의 `postgres:16-alpine`.
- 재현: `TEST_RESULTS.md`의 백엔드 명령. 4039 포트의 내장 서버 로그.
- 개선 방향: 테스트 계획에 내장 14.10과 Compose 16을 적고, 승인한 빈 16 데이터베이스에서 V1–V6를 한 번 실행한다.
- 관련 테스트: 백엔드 27개 전체.
