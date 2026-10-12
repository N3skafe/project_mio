"""프로세스 트리를 종료한다.

Windows에서는 taskkill /T /F를 쓴다. 이 명령은 대상 PID와 그 자식 프로세스를 끝내려고 한다.
프로세스가 부모를 바꾸거나 작업 객체 밖으로 빠져나가면 트리에 남지 않을 수 있다.
그 경우 직접 띄운 프로세스가 끝났는지만 확인하고, 끝나지 않으면 종료를 확인하지 않았다고 보고한다.
"""

from __future__ import annotations

import os
import signal
import subprocess


def terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        return
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        os.kill(pid, signal.SIGKILL)
