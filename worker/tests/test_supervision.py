"""상태 조회·heartbeat 예외와 출력 한도 종료를 확인한다."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from maidops_worker.loop import _execute_claimed, run_loop
from maidops_worker.runner import REASON_COMPLETED, REASON_OUTPUT_LIMIT, REASON_SUPERVISION, REASON_TIMED_OUT, run_registered_process


def _alive(pid: int) -> bool:
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
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True, text=True)


class _Api:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.finishes: list[dict[str, object]] = []
        self.status = "RUNNING"
        self.fail_finish = False
        self.fail_events = False
        self.reject_heartbeat = False

    def append_events(self, job_id: str, lines: list[tuple[str, str]]) -> None:
        if self.fail_events:
            raise RuntimeError("events down")
        self.events.extend(lines)

    def append_batch(self, job_id: str, batch_id: str, lines: list[tuple[str, str]], timeout: float = 1.0) -> None:
        self.append_events(job_id, lines)

    def finish(self, job_id: str, **kwargs: object) -> None:
        self.finishes.append(kwargs)
        if self.fail_finish:
            raise RuntimeError("finish down")

    def job_status(self, job_id: str) -> str:
        if job_id == "job-status-down":
            raise RuntimeError("status poll failed")
        return self.status

    def heartbeat_job(self, job_id: str) -> bool:
        if self.reject_heartbeat or job_id == "job-heartbeat-down":
            raise RuntimeError("heartbeat failed")
        return True


def _sleep_script(directory: Path, name: str = "sleep_job.py") -> Path:
    pid_file = directory / "pid.txt"
    script = directory / name
    script.write_text(
        "import os, time\n"
        f"open(r'{pid_file}', 'w', encoding='utf-8').write(str(os.getpid()))\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    return pid_file


def test_heartbeat_exception_stops_the_child(tmp_path: Path) -> None:
    pid_file = _sleep_script(tmp_path)
    seen = {"ready": False}

    def heartbeat() -> None:
        if pid_file.exists():
            raise RuntimeError("heartbeat failed")

    def should_cancel() -> bool:
        seen["ready"] = pid_file.exists()
        return False

    with pytest.raises(RuntimeError, match="heartbeat failed"):
        run_registered_process(
            (sys.executable, str(tmp_path / "sleep_job.py")),
            str(tmp_path),
            timeout_seconds=10,
            output_limit_bytes=1000,
            should_cancel=should_cancel,
            heartbeat=heartbeat,
            poll_seconds=0.05,
        )
    pid = int(pid_file.read_text(encoding="utf-8"))
    try:
        assert _alive(pid) is False
    finally:
        _kill(pid)


def test_output_processing_exception_stops_the_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pid_file = _sleep_script(tmp_path)

    def boom(*args, **kwargs):
        if pid_file.exists():
            raise RuntimeError("drain failed")
        return False

    monkeypatch.setattr("maidops_worker.runner._drain", boom)
    with pytest.raises(RuntimeError, match="drain failed"):
        run_registered_process(
            (sys.executable, str(tmp_path / "sleep_job.py")),
            str(tmp_path),
            timeout_seconds=10,
            output_limit_bytes=1000,
            should_cancel=lambda: False,
            heartbeat=lambda: None,
            poll_seconds=0.05,
        )
    pid = int(pid_file.read_text(encoding="utf-8"))
    try:
        assert _alive(pid) is False
    finally:
        _kill(pid)


def test_grandchild_is_stopped_when_status_poll_fails(tmp_path: Path) -> None:
    child = tmp_path / "child.py"
    child_pid = tmp_path / "child.pid"
    child.write_text(
        "import os, time\n"
        f"open(r'{child_pid}', 'w', encoding='utf-8').write(str(os.getpid()))\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    parent = tmp_path / "parent.py"
    parent.write_text(
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, r'{child}'])\n"
        "print('parent-started', flush=True)\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )

    def should_cancel() -> bool:
        if child_pid.exists():
            raise RuntimeError("status poll failed")
        return False

    with pytest.raises(RuntimeError, match="status poll failed"):
        run_registered_process(
            (sys.executable, str(parent)),
            str(tmp_path),
            timeout_seconds=20,
            output_limit_bytes=8000,
            should_cancel=should_cancel,
            heartbeat=lambda: None,
            poll_seconds=0.05,
        )
    deadline = time.monotonic() + 3
    while not child_pid.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    grandchild = int(child_pid.read_text(encoding="utf-8"))
    try:
        assert _alive(grandchild) is False
    finally:
        _kill(grandchild)


def test_stop_and_confirm_keeps_the_cleanup_error_separate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from maidops_worker.runner import _stop_and_confirm

    script = tmp_path / "sleep_job.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(script)], cwd=tmp_path)

    def broken_terminate(pid: int) -> None:
        raise RuntimeError("taskkill failed")

    def wait(timeout=None):
        raise subprocess.TimeoutExpired(process.args, timeout or 0)

    def kill():
        raise OSError("kill failed")

    monkeypatch.setattr("maidops_worker.runner.terminate_process_tree", broken_terminate)
    process.wait = wait  # type: ignore[method-assign]
    process.kill = kill  # type: ignore[method-assign]
    try:
        message = _stop_and_confirm(process)
        assert message is not None
        assert "taskkill failed" in message
        assert "종료를 확인하지 못했습니다" in message
        assert "kill failed" in message
        assert process.poll() is None
    finally:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False, capture_output=True, text=True)


def test_unconfirmed_exit_is_not_reported_as_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pid_file = _sleep_script(tmp_path)

    def leave_running(process: subprocess.Popen[str]) -> str:
        return "프로세스 트리 정리 호출에 실패했습니다: taskkill failed 프로세스 종료를 확인하지 못했습니다."

    monkeypatch.setattr("maidops_worker.runner._stop_and_confirm", leave_running)
    api = _Api()
    _execute_claimed(
        api,
        tmp_path,
        {
            "job_id": "job-status-down",
            "working_directory": ".",
            "argv": ["{python}", "sleep_job.py"],
            "timeout_seconds": 10,
        },
        output_limit_bytes=1000,
    )
    assert len(api.finishes) == 1
    assert api.finishes[0]["process_exited"] is False
    assert api.finishes[0]["termination_reason"] == REASON_SUPERVISION
    assert api.finishes[0]["termination_reason"] != REASON_COMPLETED
    texts = [text for _, text in api.events]
    assert any(text.startswith("상태 확인에 실패했습니다:") and "status poll failed" in text for text in texts)
    assert any("taskkill failed" in text and "종료를 확인하지 못했습니다" in text for text in texts)
    assert all("status poll failed" not in text or text.startswith("상태 확인에 실패했습니다:") for text in texts)
    pid = int(pid_file.read_text(encoding="utf-8"))
    try:
        assert _alive(pid) is True
    finally:
        _kill(pid)


def test_timeout_still_stops_the_process(tmp_path: Path) -> None:
    script = tmp_path / "sleep_job.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    result = run_registered_process(
        (sys.executable, str(script)),
        str(tmp_path),
        timeout_seconds=1,
        output_limit_bytes=1000,
        should_cancel=lambda: False,
        heartbeat=lambda: None,
        poll_seconds=0.05,
    )
    assert result.process_exited is True
    assert result.timed_out is True
    assert result.termination_reason == REASON_TIMED_OUT
    assert result.output_truncated is False


def test_normal_output_is_completed_without_truncation(tmp_path: Path) -> None:
    script = tmp_path / "ok.py"
    script.write_text("print('check ok')\n", encoding="utf-8")
    api = _Api()
    _execute_claimed(
        api,
        tmp_path,
        {
            "job_id": "job-ok",
            "working_directory": ".",
            "argv": ["{python}", "ok.py"],
            "timeout_seconds": 10,
        },
        output_limit_bytes=8000,
    )
    assert len(api.finishes) == 1
    assert api.finishes[0]["exit_code"] == 0
    assert api.finishes[0]["process_exited"] is True
    assert api.finishes[0]["output_truncated"] is False
    assert api.finishes[0]["termination_reason"] == REASON_COMPLETED
    assert any(text == "check ok" for _, text in api.events)


def test_small_output_limit_is_not_a_normal_success(tmp_path: Path) -> None:
    script = tmp_path / "talk.py"
    script.write_text("print('x' * 100)\nprint('y' * 100)\n", encoding="utf-8")
    api = _Api()
    _execute_claimed(
        api,
        tmp_path,
        {
            "job_id": "job-limit",
            "working_directory": ".",
            "argv": ["{python}", "talk.py"],
            "timeout_seconds": 10,
        },
        output_limit_bytes=40,
    )
    assert len(api.finishes) == 1
    finish = api.finishes[0]
    assert finish["output_truncated"] is True
    assert finish["termination_reason"] == REASON_OUTPUT_LIMIT
    assert finish["process_exited"] is True
    assert any("OUTPUT_LIMIT_EXCEEDED" in text and "보관 줄 수 제한과는 별개" in text for _, text in api.events)
    assert any("출력 잘림" in text for _, text in api.events) is False


def test_status_failure_is_reported_and_the_next_job_runs(tmp_path: Path) -> None:
    _sleep_script(tmp_path, "sleep_job.py")
    failed = _Api()
    _execute_claimed(
        failed,
        tmp_path,
        {
            "job_id": "job-status-down",
            "working_directory": ".",
            "argv": ["{python}", "sleep_job.py"],
            "timeout_seconds": 10,
        },
        output_limit_bytes=1000,
    )
    assert len(failed.finishes) == 1
    assert failed.finishes[0]["termination_reason"] == REASON_SUPERVISION
    assert failed.finishes[0]["termination_reason"] != REASON_COMPLETED
    assert any(text.startswith("상태 확인에 실패했습니다:") and "status poll failed" in text for _, text in failed.events)
    pid = int((tmp_path / "pid.txt").read_text(encoding="utf-8"))
    try:
        assert _alive(pid) is False
    finally:
        _kill(pid)

    ok = tmp_path / "ok.py"
    ok.write_text("print('next-ok')\n", encoding="utf-8")
    nxt = _Api()
    _execute_claimed(
        nxt,
        tmp_path,
        {
            "job_id": "job-next",
            "working_directory": ".",
            "argv": ["{python}", "ok.py"],
            "timeout_seconds": 10,
        },
        output_limit_bytes=8000,
    )
    assert nxt.finishes[0]["termination_reason"] == REASON_COMPLETED
    assert nxt.finishes[0]["exit_code"] == 0


def test_event_report_failure_does_not_finish_a_success(tmp_path: Path) -> None:
    script = tmp_path / "ok.py"
    script.write_text("print('check ok')\n", encoding="utf-8")
    api = _Api()
    api.fail_events = True
    _execute_claimed(
        api,
        tmp_path,
        {
            "job_id": "job-events-down",
            "working_directory": ".",
            "argv": ["{python}", "ok.py"],
            "timeout_seconds": 10,
        },
        output_limit_bytes=8000,
    )
    assert len(api.finishes) == 1
    assert api.finishes[0]["termination_reason"] == REASON_COMPLETED
    assert api.finishes[0]["log_storage_incomplete"] is True
    assert api.finishes[0]["exit_code"] == 0
    assert api.finishes[0]["process_exited"] is True
    assert api.events == []


def test_finish_api_failure_is_not_retried_as_success(tmp_path: Path) -> None:
    _sleep_script(tmp_path)
    api = _Api()
    api.fail_finish = True
    _execute_claimed(
        api,
        tmp_path,
        {
            "job_id": "job-status-down",
            "working_directory": ".",
            "argv": ["{python}", "sleep_job.py"],
            "timeout_seconds": 10,
        },
        output_limit_bytes=1000,
    )
    assert len(api.finishes) == 1
    assert api.finishes[0]["termination_reason"] == REASON_SUPERVISION
    assert api.finishes[0]["termination_reason"] != REASON_COMPLETED
    pid = int((tmp_path / "pid.txt").read_text(encoding="utf-8"))
    try:
        assert _alive(pid) is False
    finally:
        _kill(pid)


def test_cancel_still_prevents_a_late_success_line(tmp_path: Path) -> None:
    script = tmp_path / "slow.py"
    script.write_text(
        "import time\nprint('slow-start', flush=True)\ntime.sleep(30)\nprint('slow-done', flush=True)\n",
        encoding="utf-8",
    )
    armed = {"n": 0}

    def should_cancel() -> bool:
        armed["n"] += 1
        return armed["n"] >= 2

    result = run_registered_process(
        (sys.executable, str(script)),
        str(tmp_path),
        timeout_seconds=10,
        output_limit_bytes=8000,
        should_cancel=should_cancel,
        heartbeat=lambda: None,
        poll_seconds=0.05,
    )
    assert result.process_exited is True
    assert result.timed_out is False
    assert result.termination_reason != REASON_TIMED_OUT
    assert all(line.text != "slow-done" for line in result.lines)


def test_worker_loop_continues_after_a_job_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def execute(api, root, claimed, limit) -> None:
        seen.append(str(claimed["job_id"]))
        if claimed["job_id"] == "job-1":
            raise RuntimeError("boom")

    monkeypatch.setattr("maidops_worker.loop._execute_claimed", execute)

    class Api:
        def __init__(self) -> None:
            self.queue = ["job-1", "job-2"]

        def heartbeat(self) -> None:
            return None

        def claim(self):
            if self.queue:
                return {"job_id": self.queue.pop(0)}
            return None

        def close(self) -> None:
            return None

    run_loop(
        base_url="http://127.0.0.1:9",
        workspace_root=tmp_path,
        api=Api(),  # type: ignore[arg-type]
        stop_on_empty=True,
        idle_seconds=0.01,
    )
    assert seen == ["job-1", "job-2"]
