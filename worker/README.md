# worker

등록된 테스트 명령만 실행하는 Python 워커입니다. 사용자 입력을 셸 문자열로 실행하지 않습니다.

실행 파일은 `{python}` 토큰 하나만 허용하고, 워커가 자신의 `sys.executable`로 바꿉니다. 스크립트는 `MAIDOPS_WORKSPACE_ROOT` 안의 파일이어야 합니다. `subprocess`는 `shell=False`입니다.

## Windows

```powershell
cd worker
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
$env:MAIDOPS_BACKEND_URL = "http://127.0.0.1:8080"
$env:MAIDOPS_WORKSPACE_ROOT = "..\fixtures\trusted-projects"
.\.venv\Scripts\python -m maidops_worker
```

`MAIDOPS_WORKSPACE_ROOT`는 저장소의 `fixtures/trusted-projects`를 가리켜야 하고, 백엔드의 같은 환경 변수와 같아야 합니다.

## 동작

- `POST /api/v1/worker/claim`은 `QUEUED`이면서 argv가 있는 작업을 `FOR UPDATE SKIP LOCKED`로 한 건만 `RUNNING`으로 바꿉니다.
- 실행 중에는 임대 시각을 갱신합니다.
- stdout과 stderr는 읽힌 순서대로 이벤트로 저장합니다. 출력량 한도를 넘으면 잘렸다고 표시하고 프로세스를 멈춥니다.
- 종료 코드 0은 `SUCCEEDED`, 그 외와 타임아웃은 `FAILED`입니다. 실패 사례에는 로그와 `exit_code`가 들어갑니다.
- 취소 요청은 `CANCEL_REQUESTED`입니다. 프로세스 트리가 끝난 뒤에만 `CANCELLED`가 됩니다. 종료 코드 0이어도 성공으로 바꾸지 않습니다.
- Windows에서는 `taskkill /PID <pid> /T /F`로 자식 프로세스를 끝냅니다. 프로세스가 부모를 바꾸거나 작업 객체 밖으로 빠지면 트리에 남지 않을 수 있습니다. 직접 띄운 프로세스가 5초 안에 끝나지 않으면 종료를 확인하지 않았다고 기록하고 `CANCELLED`로 바꾸지 않습니다.
- 임대가 만료된 `RUNNING` 또는 `CANCEL_REQUESTED` 작업은 `FAILED`가 되고 대기열로 되돌리지 않습니다.

신뢰하는 fixture는 `fixtures/trusted-projects/sample`의 `pass_check.py`, `fail_check.py`, `slow_check.py`입니다.
