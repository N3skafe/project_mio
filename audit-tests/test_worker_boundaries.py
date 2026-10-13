"""워커 안전 경계. 제품 코드는 호출만 하고 수정하지 않는다."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from maidops_worker.command import CommandRejected, resolve_command
from maidops_worker.loop import _execute_claimed
from maidops_worker.masking import mask_secrets
from maidops_worker.runner import run_registered_process


class _Api:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.finish_kwargs: dict[str, object] | None = None

    def append_events(self, job_id: str, lines: list[tuple[str, str]]) -> None:
        self.events.extend(lines)

    def finish(self, job_id: str, **kwargs: object) -> None:
        self.finish_kwargs = kwargs

    def job_status(self, job_id: str) -> str:
        return "RUNNING"

    def heartbeat_job(self, job_id: str) -> bool:
        return True


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    completed = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return str(pid) in completed.stdout


def _kill(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        check=False,
        capture_output=True,
        text=True,
    )


def test_status_poll_error_stops_the_child_and_enforces_timeout(tmp_path: Path) -> None:
    """상태 조회가 실패해도 자식 프로세스가 남고 타임아웃 감시가 끊기면 안 된다."""
    pid_file = tmp_path / "pid.txt"
    script = tmp_path / "sleep_job.py"
    script.write_text(
        "import os, time\n"
        f"open(r'{pid_file}', 'w', encoding='utf-8').write(str(os.getpid()))\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )

    def should_cancel() -> bool:
        if pid_file.exists():
            raise RuntimeError("status poll failed")
        return False

    with pytest.raises(RuntimeError, match="status poll failed"):
        run_registered_process(
            (sys.executable, str(script)),
            str(tmp_path),
            timeout_seconds=2,
            output_limit_bytes=1000,
            should_cancel=should_cancel,
            heartbeat=lambda: None,
            poll_seconds=0.05,
        )
    assert pid_file.exists()
    pid = int(pid_file.read_text(encoding="utf-8"))
    try:
        assert _alive(pid) is False
    finally:
        _kill(pid)


def test_cancel_kills_a_grandchild_process(tmp_path: Path) -> None:
    parent = tmp_path / "parent.py"
    child = tmp_path / "child.py"
    child_pid = tmp_path / "child.pid"
    child.write_text(
        "import os, time\n"
        f"open(r'{child_pid}', 'w', encoding='utf-8').write(str(os.getpid()))\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    parent.write_text(
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, r'{child}'])\n"
        "print('parent-started', flush=True)\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    started = {"ok": False}

    def should_cancel() -> bool:
        return started["ok"] and child_pid.exists()

    def heartbeat() -> None:
        started["ok"] = True

    result = run_registered_process(
        (sys.executable, str(parent)),
        str(tmp_path),
        timeout_seconds=20,
        output_limit_bytes=8000,
        should_cancel=should_cancel,
        heartbeat=heartbeat,
        poll_seconds=0.05,
    )
    deadline = time.monotonic() + 3
    while not child_pid.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert child_pid.exists()
    grandchild = int(child_pid.read_text(encoding="utf-8"))
    try:
        assert result.process_exited is True
        assert _alive(grandchild) is False
    finally:
        _kill(grandchild)


def test_byte_limit_is_visible_on_finish(tmp_path: Path) -> None:
    script = tmp_path / "talk.py"
    script.write_text(
        "print('x' * 100)\nprint('y' * 100)\n",
        encoding="utf-8",
    )
    api = _Api()
    _execute_claimed(
        api,
        tmp_path,
        {
            "job_id": "job-audit-1",
            "working_directory": ".",
            "argv": ["{python}", "talk.py"],
            "timeout_seconds": 10,
        },
        output_limit_bytes=40,
    )
    assert api.finish_kwargs is not None
    assert api.finish_kwargs.get("output_truncated") is True


def test_uri_password_is_masked() -> None:
    raw = "postgresql://app:supersecret@127.0.0.1:5432/maidops"
    assert "supersecret" not in mask_secrets(raw)


def test_symlink_script_outside_root_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    work = root / "sample"
    work.mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("print('escaped')\n", encoding="utf-8")
    link = work / "escaped.py"
    try:
        os.symlink(outside, link)
    except OSError as exc:
        pytest.skip(f"이 계정에서는 symlink를 만들지 못했습니다: {exc}")
    with pytest.raises(CommandRejected):
        resolve_command(root, "sample", ["{python}", "escaped.py"])


def test_shell_operator_and_parent_directory_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "sample").mkdir(parents=True)
    script = root / "sample" / "ok.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    with pytest.raises(CommandRejected):
        resolve_command(root, "sample", ["{python}", "ok.py", "a && b"])
    with pytest.raises(CommandRejected):
        resolve_command(root, "sample", ["cmd.exe", "ok.py"])
    with pytest.raises(CommandRejected):
        resolve_command(root, "..", ["{python}", "ok.py"])
