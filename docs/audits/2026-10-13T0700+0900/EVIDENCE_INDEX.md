# 증거 색인

로그와 보고서에 저장소 비밀번호를 다시 적지 않았다. 마스킹 테스트의 `supersecret`은 소스에 넣은 가짜 값이다. `.env`는 읽지 않았다. 파일 내용을 외부로 보내지 않았다.

정적 증거는 소스와 문서다. 실행 증거는 이번 세션의 종료 코드와 출력이다.

| 주장 | 구분 | 증거 |
| --- | --- | --- |
| 대상 commit과 시작 시 깨끗한 트리 | 실행 | `git status`, `git rev-parse HEAD` → `ab1d66090e296f3a73aef14dad59130eae2cc34d` |
| 제품 코드를 수정하지 않음 | 실행 | 감사 종료 시점 `git status --short`는 `?? audit-tests/`와 이 보고서 디렉터리뿐 |
| DEMO pytest가 Java 없이 돈다 | 실행 | TUI pytest 58 passed. 실패 1건은 F-10 |
| 좁은 레이아웃 테스트가 간헐 실패 | 실행 | 6회 중 2회 실패, 실패 회차 0.42s. F-10 |
| 취소 앱 테스트 1회 실패는 재현되지 않음 | 실행 | 단독 8회 모두 종료 코드 0 |
| CPU 소형 학습 스모크 | 실행 | trainer pytest 7 passed, 3.00s. NumPy 경고 |
| 워커 fixture 4개 | 실행 | TUI 인터프리터 + `worker/src`. `worker/.venv`는 기준 Python 부재로 미사용 |
| 백엔드 27개와 Flyway | 실행 | `mvnw -o test` BUILD SUCCESS. 내장 PostgreSQL 14.10, 포트 4039, DB 이름 `postgres` |
| 내장 DB가 사용자 5432가 아님 | 실행 | JDBC URL `localhost:4039/postgres`. 종료 후 4039 listen 없음 |
| 기동 중 스택은 관찰만 | 실행 | `docker ps`. health JSON `database=UP`, `worker=CONNECTED`, `authentication=NONE`. POST 없음 |
| 호스트 포트가 루프백만 | 실행 | `Get-NetTCPConnection` LocalAddress `127.0.0.1`, LocalPort 8080과 5432 |
| F-01 프로세스 잔존 | 실행 | 감사 테스트 실패 출력. PID 13504가 예외 직후 살아 있음. `finally` 정리 후 tasklist에 없음 |
| F-02 macro F1 = 1.0 | 실행 | Python `from_confusion` 출력. Java는 같은 조건의 정적 대조 |
| F-03 URI 미마스킹 | 실행 | 감사 테스트 AssertionError에 가짜 비밀이 포함된 입력 문자열이 보임 |
| F-04 finish에 잘림 없음, exit 0 | 실행 | finish dict `exit_code=0`, `process_exited=True`, `timed_out=False` |
| symlink·손자 프로세스·셸 거부 | 실행 | 감사 테스트 5개 통과 |
| 규칙 우선순위 | 실행 | Java `FailureRuleClassifierTest` 2, trainer 규칙 테스트, 감사 테스트 2 |
| 기본 모델 자동 교체 없음 | 실행 | `TrainingLabIntegrationTest`가 더미 바이트로 플래그만 확인. F-09 |
| 모델 초안이 확정 라벨이 아님 | 실행 | `ModelDraftIntegrationTest` 1 passed. 라벨은 테스트가 JSON으로 제출 |
| 문서가 모델 초안과 다름 | 정적 | `README.md` 157–161, `PROJECT.md` 9, `ModelDraftService.java` 78–104, `ROADMAP.md` 26 |
| SECURITY의 argv 문장이 오래됨 | 정적 | `SECURITY.md` 6, `V2__worker_queue.sql` 9 |
| JDK 스크립트 경로 부재 | 실행 | `Test-Path` False/True. JDK 11 컴파일은 미실행 |
| 검토 충돌 정책 없음 | 정적 | `ErrorCaseService.review` 70–80. 병렬 HTTP 미실행 |
| 출력이 종료 후 한 번에 전송 | 정적 | `loop.py` 72–86. 워커 kill 미실행 |
| 검색 SQL이 파라미터 | 정적 | repository `:query`와 escape. 대량·따옴표 payload 미실행 |
| 외부 LLM 호출 없음 | 정적 | 소스 검색과 ROADMAP. 이번 세션에서 해당 호출 없음 |
| CUDA 불가 | 실행 | `torch.cuda.is_available()` False |
| PostgreSQL 16 빈 DB 마이그레이션 | 미실행 | 5432는 개발 DB. health UP은 스키마 버전 조회가 아님 |
| 실제 터미널 목시 | 미실행 | headless만 수행. 수동 목록은 `REPRODUCTION.md` |

## 감사 중 만든 것

| 종류 | 이름 | 정리 |
| --- | --- | --- |
| 파일 | `audit-tests/test_worker_boundaries.py` | 유지. 제품 코드 아님 |
| 파일 | `audit-tests/test_metrics_and_rules.py` | 유지 |
| 파일 | `docs/audits/2026-10-13T0700+0900/*.md` | 이 보고서 |
| 프로세스 | Zonky PostgreSQL, 포트 4039, Windows PID는 Maven 자식 | JVM 종료 후 포트가 닫힘 |
| 프로세스 | 감사 테스트의 sleep·자식 Python | 실패 테스트의 `finally`와 통과한 취소 테스트가 `taskkill /T /F` |
| DB | 내장 클러스터 데이터 디렉터리는 사용자 임시 폴더 | 사용자 `maidops` 볼륨과 다름. 포트가 닫힌 것만 확인 |
| 컨테이너 | 없음 | 기존 `infra-*` 4개는 중지·삭제하지 않음 |
| 모델 다운로드 | 없음 | trainer 테스트가 임시 디렉터리에 작은 `.pt`를 만들고 pytest가 삭제 |

`backend/target`의 surefire 텍스트는 이번 `mvnw test`가 갱신했다. 저장소 추적 대상이 아니면 `git status`에 나타나지 않는다. 제품 소스는 포함하지 않는다.

## 마스킹

보고서에 개발 DB 비밀번호를 다시 쓰지 않았다. health 본문에는 비밀번호가 없었다. F-03의 실패 출력에 보이는 비밀번호는 테스트가 만든 단어 `supersecret`이다.
