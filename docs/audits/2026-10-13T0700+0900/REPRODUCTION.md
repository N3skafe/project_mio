# 재현 절차

제품 코드는 바꾸지 않는다. 아래 감사 테스트는 이미 `audit-tests/`에 있다. 사용자 DB `127.0.0.1:5432`와 개발 API `127.0.0.1:8080`에는 요청을 보내지 않는다. health GET은 이미 한 번 했으므로 재현에 다시 넣을 필요는 없다.

공통 준비:

```powershell
cd "F:\Artificial Intelligence\project_mio"
$env:PYTHONPATH = "F:\Artificial Intelligence\project_mio\worker\src;F:\Artificial Intelligence\project_mio\trainer\src"
$py = "F:\Artificial Intelligence\project_mio\tui\.venv\Scripts\python.exe"
```

## F-01 상태 조회 예외 뒤 프로세스 잔존

필요 fixture: 없음. 테스트가 임시 디렉터리에 sleep 스크립트를 만든다.

```powershell
& $py -m pytest audit-tests/test_worker_boundaries.py::test_status_poll_error_stops_the_child_and_enforces_timeout -q --tb=short
```

예상(요구사항): 자식이 종료되어 테스트가 통과한다.  
실제: 실패.

```text
assert _alive(pid) is False
assert True is False
```

이번 실행의 PID는 13504였다. 테스트의 `finally`가 `taskkill /PID <pid> /T /F`를 호출한다. 재현 직후 `tasklist /FI "PID eq 13504"`는 그 프로세스가 없었다.

## F-02 macro F1이 1.0으로 남음

```powershell
& $py -m pytest audit-tests/test_metrics_and_rules.py::test_supported_class_with_no_predictions_lowers_macro_f1 -q --tb=short
```

예상: INPUT F1이 0이고 macro F1이 2/3이다.  
실제:

```text
ClassScore(label='INPUT_VALIDATION', precision=None, recall=0.0, f1=None, support=2)
macro 1.0
```

같은 행렬의 클래스별 값은 DB F1 1.0 support 2, AUTH F1 1.0 support 2, EXTERNAL support 0, OTHER support 0이다. Java `ClassificationMetrics.fromConfusion`은 같은 `support > 0 && f1 != null` 조건을 쓴다. 이번 감사에서 그 Java 메서드에 이 행렬을 넣어 실행하지는 않았다.

## F-03 URI 비밀번호

```powershell
& $py -m pytest audit-tests/test_worker_boundaries.py::test_uri_password_is_masked -q --tb=short
```

예상: 마스킹 결과에 `supersecret`이 없다.  
실제: `postgresql://app:supersecret@127.0.0.1:5432/maidops`가 그대로다. `supersecret`은 테스트 문자열이다.

## F-04 잘림이 없는 성공 finish

```powershell
& $py -m pytest audit-tests/test_worker_boundaries.py::test_byte_limit_is_visible_on_finish -q --tb=short
```

예상: finish 인자의 `output_truncated`가 참이다.  
실제:

```text
{'exit_code': 0, 'process_exited': True, 'timed_out': False}
output_truncated 키 없음
```

fixture는 임시 디렉터리의 `talk.py`가 `x` 100자와 `y` 100자를 출력한다. 한도는 40바이트다.

## F-05 문서 불일치

코드를 실행하지 않아도 된다. 다음을 나란히 연다.

- `README.md` 157–161행, `docs/PROJECT.md` 9행: 학습 모델이 새 로그를 분류하지 않는다고 적혀 있다.
- `backend/src/main/java/lab/maidops/lab/ModelDraftService.java` 78–104행: 기본 모델과 파일이 있으면 MODEL 초안을 큐에 넣는다.
- `docs/SECURITY.md` 6행과 `backend/src/main/resources/db/migration/V2__worker_queue.sql` 9행.

## F-06 JDK 경로

```powershell
Test-Path "C:\Program Files\Java\jdk-21"
Test-Path "C:\Program Files\Java\jdk-21.0.12.1"
```

실제: 첫 값은 False, 둘째는 True. `scripts/test-backend.ps1`은 첫 경로만 본다. JDK 11로 Maven을 실패시키는 실행은 하지 않았다.

백엔드 테스트 재현은 사용자 DB와 무관하다.

```powershell
$env:JAVA_HOME = "C:\Program Files\Java\jdk-21.0.12.1"
$env:Path = "$env:JAVA_HOME\bin;" + $env:Path
.\backend\mvnw.cmd -f .\backend\pom.xml -B -o test
```

실제: Tests run 27, BUILD SUCCESS. 내장 PostgreSQL 14.10, 포트 4039. 이 값을 셸에 남기지 않으려면 끝난 뒤 `JAVA_HOME`을 원래 값으로 되돌린다.

## F-07 검토 충돌

이번 감사에서는 실행하지 않았다. 사용자 DB에 쓰지 않기 위해서다. 빈 내장 DB를 다시 띄울 수 있을 때의 절차는 다음과 같다.

1. 내장 또는 감사 전용 DB에서 실패 사례 하나를 DRAFT로 만든다.
2. 같은 사례에 승인 요청과 다른 라벨 수정 요청을 동시에 보낸다.
3. 현재 코드는 revision 조건을 보지 않으므로 둘 다 200이 되고, 나중 트랜잭션의 `current_label`만 남는다.

## F-08 출력의 지연 전송

이번 감사에서는 워커를 죽이지 않았다. 코드 순서는 `loop.py`의 `run_registered_process` 완료 다음 `append_events`, 그 다음 `finish`다. 실행 재현은 감사 전용 스택에서 긴 출력을 내는 등록 스크립트를 claim한 직후, events POST 전에 워커 프로세스만 종료하면 된다. 기존 5432 스택에서는 하지 않는다.

## F-09 더미 파일과 점수

`backend` 테스트 `trainingDoesNotReplaceTheDefaultModel`가 이미 그 경로다. 모델 파일 내용은 `not-a-loaded-checkpoint`이고 complete는 미리 계산한 행렬을 보낸다. 테스트는 200과 `is_default=false`를 기대하고, 이번 실행에서 통과했다.

## F-10 Textual 대기

```powershell
cd tui
$env:PYTHONPATH = "src"
1..6 | ForEach-Object { .\.venv\Scripts\python.exe -m pytest tests/test_app.py::test_narrow_layout_still_accepts_commands -q --tb=line }
```

실제: 6회 중 2회 실패. 실패 단언은 활동 로그에 `도움말`이 없는 것이다. 실패 회차는 약 0.42초였다.

## 통과한 감사 재현

다음 5개는 이번 실행에서 통과했다.

- `test_digits_touching_status_codes_do_not_match_auth`
- `test_keyword_priority_prefers_auth_over_database`
- `test_cancel_kills_a_grandchild_process`
- `test_symlink_script_outside_root_is_rejected`
- `test_shell_operator_and_parent_directory_are_rejected`

symlink 테스트는 이 계정이 `os.symlink`에 성공했다. 권한이 없는 계정에서는 skip이며, 그때는 이 항목이 BLOCKED다.

## 수동 터미널 확인

headless Textual은 글꼴, 줄바꿈, 색 대비, 입력기 조합을 대체하지 않는다. DEMO만 확인할 때는 백엔드를 띄우지 않는다.

```powershell
cd tui
$env:MAIDOPS_MODE = "DEMO"
$env:MAIDOPS_QUIET = "false"
chcp 65001
.\.venv\Scripts\python.exe -m maidops_tui
```

확인할 것:

1. 위 줄에 `DEMO(가상, 백엔드 없음)`이 보인다.
2. F2–F5로 Workspace, Review, Lab, History가 바뀌고 명령 입력은 지워지지 않는다.
3. F1 도움말에 `/cancel`이 있고 Escape로 닫힌다.
4. `/nope`은 앱을 종료하지 않고 예시를 보여 준다.
5. `demo-api`에서 `/test` 후 로그에 `RESULT FAIL`이 있고, 그 전에 `/cancel job-0001`을 누르면 나중에 PASS로 바뀌지 않는다.
6. 승인 뒤 활동 로그는 학습을 시작하지 않는다고 말하고, Lab 버튼은 꺼져 있으며 F1 숫자가 없다.
7. `/quiet on`은 대사만 숨긴다.
8. 창 너비를 78칸 근처로 줄여도 상태와 명령, Lab의 비활성 버튼에 키보드로 갈 수 있다.
9. 한글 프로젝트 이름과 ASCII 캐릭터가 깨지지 않는다.

LIVE 확인은 격리 포트가 승인된 뒤에 한다. 이미 떠 있는 8080에 DEMO가 아닌 모드로 붙으면 개발 DB에 작업이 생긴다.

## 재현하지 않은 이유

| 항목 | 이유 |
| --- | --- |
| 빈 PostgreSQL 16 마이그레이션 | 5432는 사용 중인 개발 DB. 다른 포트의 새 볼륨은 승인 전 |
| LIVE 17단계 | 같은 이유. health GET만 수행 |
| 워커 프로세스 강제 종료 | 개발 워커 컨테이너를 멈추지 않음 |
| CUDA | `torch.cuda.is_available()` 거짓 |
| JDK 11 Maven 실패 문구 | 실패를 만들기 위한 실행은 하지 않음. 경로 부재는 확인 |
| 사람 눈의 TUI | 이 세션에서 대화형 터미널을 조작하지 않음 |
