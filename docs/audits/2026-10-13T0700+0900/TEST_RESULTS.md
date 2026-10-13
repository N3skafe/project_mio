# 테스트 실행 기록

모든 명령은 2026-10-13 KST에 실행했다. 사용자 `JAVA_HOME`으로 Maven을 돌리지 않았다. 백엔드 명령에서만 프로세스 환경 변수를 JDK 21.0.12.1로 지정했다. 종료 후 에이전트 셸의 `JAVA_HOME`과 PATH는 JDK 11 기준으로 되돌렸다.

네트워크로 의존성을 받지 않았다. Maven은 `-o`다. 기동 중 Docker 스택에는 `GET /api/v1/health` 한 번만 보냈다.

## 1. TUI pytest 첫 실행

- 명령: `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m pytest -q --tb=line`
- 작업 디렉터리: `tui`
- 실행: 예
- 종료 코드: 1
- 결과: 1 failed, 58 passed, 7.77s
- 실패: `tests/test_app.py::test_cancel_from_command_is_not_reported_as_pass` (`jobs[0]` IndexError)
- DB·모델·모드: DEMO. DB 없음. 모델 없음
- 해석: 이 실행은 trainer·worker pytest와 같은 시각에 다른 작업 디렉터리로 함께 시작했다. 이후 이 테스트만 8회는 모두 통과했다. 첫 실패를 제품의 취소 결함으로 단정하지 않는다. F-10.

## 2. TUI 취소 테스트 재실행

- 명령: 같은 인터프리터로 `tests/test_app.py::test_cancel_from_command_is_not_reported_as_pass`를 8회
- 작업 디렉터리: `tui`
- 실행: 예
- 종료 코드: 마지막 포함 각 회 0
- 결과: PASS 8, FAIL 0. 회당 약 0.57–0.78s
- 해석: 격리하면 취소 후 `CANCELLED`와 `RESULT PASS` 부재 단언이 유지됐다.

## 3. TUI pytest 두 번째 전체 실행

- 명령: 1번과 같음. 단독 실행
- 작업 디렉터리: `tui`
- 실행: 예
- 종료 코드: 1
- 결과: 1 failed, 58 passed, 7.33s
- 실패: `tests/test_app.py::test_narrow_layout_still_accepts_commands`
- 해석: 59개 중 앱 테스트 1개가 불안정하다. 나머지 58개에는 파서, DEMO 서비스, 캐릭터, API 서비스 Mock, 규칙이 포함된다.

## 4. 좁은 레이아웃 테스트 6회

- 명령: `tests/test_app.py::test_narrow_layout_still_accepts_commands` 6회
- 작업 디렉터리: `tui`
- 실행: 예
- 결과: PASS 4, FAIL 2
- 통과 시간: 0.57s, 0.52s, 0.54s, 0.49s
- 실패 시간: 0.42s, 0.42s
- 종료 코드: 실패가 섞여 마지막 회차가 1
- 해석: F-10. 78x24에서 명령이 항상 무시되는 결과로는 보지 않는다.

## 5. Trainer pytest

- 명령: `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m pytest -q --tb=line`
- 작업 디렉터리: `trainer`
- 실행: 예
- 종료 코드: 0
- 결과: 7 passed, 1 warning, 3.00s
- 경고: NumPy 없음. torch 2.14.1+cpu
- DB·모델·모드: 임시 디렉터리의 `mv-00000001.pt`. CPU. CUDA 아님
- 해석: 분리 가능한 소형 데이터의 학습→저장→로드→argmax와, CUDA 미설치 시 `cuda` 요청 거절이 통과했다. 일반화 성능 수치가 아니다.

## 6. Worker pytest

- 명령: `$env:PYTHONPATH = "src"; ..\tui\.venv\Scripts\python.exe -m pytest -q --tb=short`
- 작업 디렉터리: `worker`
- 실행: 예. `worker/.venv`의 python.exe는 기준 인터프리터가 없어 쓰지 않았다
- 종료 코드: 0
- 결과: 4 passed, 0.38s
- DB·모델: 없음. fixture는 `fixtures/trusted-projects`
- 해석: 셸 거부, pass/fail exit code, slow fixture 취소, 대입문 마스킹. URI 마스킹과 예외 시 프로세스 정리는 여기 없다.

## 7. Backend Maven 테스트

- 명령: `JAVA_HOME=C:\Program Files\Java\jdk-21.0.12.1` 로 `.\backend\mvnw.cmd -f .\backend\pom.xml -B -o test`
- 작업 디렉터리: 저장소 루트
- 실행: 예
- 종료 코드: 0
- Maven 전체 시간: 19.110s. 종료 시각 2026-10-13T06:57:12+09:00
- 클래스별 (surefire):

| 클래스 | 개수 | 실패 | 시간 |
| --- | --- | --- | --- |
| ApiIntegrationTest | 16 | 0 | 13.60s |
| ClassificationMetricsTest | 2 | 0 | 0.006s |
| DatasetSplitterTest | 3 | 0 | 0.017s |
| FailureRuleClassifierTest | 2 | 0 | 0.003s |
| ModelDraftIntegrationTest | 1 | 0 | 1.064s |
| TrainingLabIntegrationTest | 3 | 0 | 1.380s |
| 합계 | 27 | 0 | |

- DB: Zonky PostgreSQL 14.10, `jdbc:postgresql://localhost:4039/postgres`, 사용자 `postgres`. 빈 클러스터에 Flyway 6개 적용. 이후 컨텍스트는 “Schema public is up to date”.
- 모델: 테스트가 텍스트 바이트를 `mv-*.pt`로 저장. PyTorch 로드 없음
- 모드: MockMvc. 호스트 8080의 개발 서버에 요청하지 않음
- 정리: 테스트 JVM 종료 후 포트 4039는 listen 중이 아님
- 해석: API·큐·규칙·분할·학습 상태 기계의 증거다. F-02의 행렬과 F-09의 더미 파일 한계를 통과로 덮지 않는다. PostgreSQL 16은 이 명령의 대상이 아니다.

## 8. 감사 테스트

- 명령: `PYTHONPATH=worker\src;trainer\src` 로 `tui\.venv\Scripts\python.exe -m pytest -q --tb=short`
- 작업 디렉터리: `audit-tests`
- 실행: 예
- 종료 코드: 1
- 결과: 4 failed, 5 passed, 1.21s
- 통과: 상태 코드 숫자 경계, 규칙 우선순위, 손자 프로세스 취소, symlink 거부, 셸 연산자·상위 경로 거부
- 실패: F-01, F-02, F-03, F-04의 기대 동작을 단언한 테스트
- DB·모델: 없음. 로컬 프로세스만 생성하고 `finally`에서 `taskkill /T /F`. 이후 PID 13504는 없음
- 해석: 실패 4건은 제품 결함의 재현이다. 감사 테스트를 제품 결함으로 고치라는 뜻이 아니다.

## 9. 읽기 전용 health

- 명령: `Invoke-RestMethod http://127.0.0.1:8080/api/v1/health`
- 실행: 예
- 본문: `{"database":"UP","status":"UP","authentication":"NONE","worker":"CONNECTED"}`
- 해석: 이미 떠 있는 개발 스택의 관찰이다. 작업을 만들지 않았고 DB에 접속하지 않았다.

## 실행하지 않은 테스트

- `scripts/test-backend.ps1` 원문. JDK 경로가 없어 사용자 JDK 11로 넘어간다. JDK 11 컴파일 실패는 일부러 실행하지 않았다.
- `scripts/test-tui.ps1`, `scripts/test-trainer.ps1`. 같은 pytest를 venv 경로로 직접 실행했다.
- Docker Compose 기동, 이미지 pull, 사용자 DB 마이그레이션, 워커·학습기 재시작.
- CUDA 학습, 외부 LLM, 모델 다운로드.
- 실제 터미널의 목시 확인.
- Idempotency 병렬 요청, 검토 병렬 요청, 워커를 결과 저장 전에 죽이는 실험.
