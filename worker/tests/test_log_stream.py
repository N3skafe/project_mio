"""실행 중 로그 배치. 프로세스 재실행은 하지 않는다."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from maidops_worker.client import BatchRejected
from maidops_worker.loop import _execute_claimed
from maidops_worker.runner import REASON_COMPLETED, REASON_OUTPUT_LIMIT, REASON_SUPERVISION, REASON_TIMED_OUT


class _StreamApi:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.batches: list[tuple[str, tuple[tuple[str, str], ...]]] = []
        self.finishes: list[dict[str, object]] = []
        self.stored: dict[str, tuple[tuple[str, str], ...]] = {}
        self.lose_once = False
        self.fail_remaining = 0
        self.always_fail = False
        self.delay = 0.0
        self.status = "RUNNING"
        self._lock = threading.Lock()

    def heartbeat_job(self, job_id: str) -> bool:
        return True

    def job_status(self, job_id: str) -> str:
        if job_id == "job-status-down":
            raise RuntimeError("status poll failed")
        return self.status

    def append_batch(self, job_id: str, batch_id: str, lines: list[tuple[str, str]], timeout: float = 1.0) -> None:
        del job_id, timeout
        if self.delay:
            time.sleep(self.delay)
        payload = tuple(lines)
        with self._lock:
            if self.always_fail:
                raise RuntimeError("log down")
            if self.fail_remaining:
                self.fail_remaining -= 1
                raise RuntimeError("temporary")
            previous = self.stored.get(batch_id)
            if previous is not None:
                if previous != payload:
                    raise BatchRejected("CONFLICT")
                return
            if self.lose_once:
                self.stored[batch_id] = payload
                self.events.extend(lines)
                self.batches.append((batch_id, payload))
                self.lose_once = False
                raise RuntimeError("response lost")
            self.stored[batch_id] = payload
            self.batches.append((batch_id, payload))
            self.events.extend(lines)

    def finish(self, job_id: str, **kwargs: object) -> None:
        del job_id
        self.finishes.append(kwargs)


def _claimed(job_id: str, script: str, timeout: int = 10) -> dict[str, object]:
    return {
        "job_id": job_id,
        "working_directory": ".",
        "argv": ["{python}", script],
        "timeout_seconds": timeout,
    }


def test_first_line_is_sent_before_the_process_exits(tmp_path: Path) -> None:
    script = tmp_path / "ticks.py"
    script.write_text(
        "import time\nprint('tick-1', flush=True)\ntime.sleep(1.2)\nprint('tick-2', flush=True)\n",
        encoding="utf-8",
    )
    api = _StreamApi()
    done = threading.Event()

    def run() -> None:
        _execute_claimed(api, tmp_path, _claimed("job-ticks", "ticks.py"), 8000)
        done.set()

    threading.Thread(target=run, daemon=True).start()
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and not any(text == "tick-1" for _, text in api.events):
        time.sleep(0.05)
    assert any(text == "tick-1" for _, text in api.events)
    assert done.is_set() is False
    assert done.wait(3)
    texts = [text for _, text in api.events]
    assert texts.index("tick-1") < texts.index("tick-2")
    assert api.finishes[0]["termination_reason"] == REASON_COMPLETED
    assert api.finishes[0]["log_storage_incomplete"] is False


def test_lost_response_retries_the_same_batch_once(tmp_path: Path) -> None:
    script = tmp_path / "ok.py"
    script.write_text("print('only-once', flush=True)\n", encoding="utf-8")
    api = _StreamApi()
    api.lose_once = True
    _execute_claimed(api, tmp_path, _claimed("job-lost", "ok.py"), 8000)
    assert [text for _, text in api.events].count("only-once") == 1
    assert api.finishes[0]["log_storage_incomplete"] is False


def test_temporary_failure_recovers(tmp_path: Path) -> None:
    script = tmp_path / "ok.py"
    script.write_text("print('recovered', flush=True)\n", encoding="utf-8")
    api = _StreamApi()
    api.fail_remaining = 1
    _execute_claimed(api, tmp_path, _claimed("job-retry", "ok.py"), 8000)
    assert any(text == "recovered" for _, text in api.events)
    assert api.finishes[0]["termination_reason"] == REASON_COMPLETED
    assert api.finishes[0]["log_storage_incomplete"] is False


def test_persistent_failure_limits_retries_and_keeps_the_process_result(tmp_path: Path) -> None:
    script = tmp_path / "ok.py"
    script.write_text("print('unsent', flush=True)\n", encoding="utf-8")
    api = _StreamApi()
    api.always_fail = True
    started = time.monotonic()
    _execute_claimed(api, tmp_path, _claimed("job-down", "ok.py"), 8000)
    elapsed = time.monotonic() - started
    assert elapsed < 8
    assert api.finishes[0]["termination_reason"] == REASON_COMPLETED
    assert api.finishes[0]["exit_code"] == 0
    assert api.finishes[0]["log_storage_incomplete"] is True
    assert api.events == []


def test_slow_send_does_not_hold_the_process_timeout(tmp_path: Path) -> None:
    script = tmp_path / "sleep_job.py"
    script.write_text("import time\nprint('late', flush=True)\ntime.sleep(30)\n", encoding="utf-8")
    api = _StreamApi()
    api.delay = 2.0
    started = time.monotonic()
    _execute_claimed(api, tmp_path, _claimed("job-slow-post", "sleep_job.py", timeout=1), 8000)
    elapsed = time.monotonic() - started
    assert elapsed < 8
    assert api.finishes[0]["timed_out"] is True
    assert api.finishes[0]["termination_reason"] == REASON_TIMED_OUT


def test_cancel_during_send_does_not_leave_a_success(tmp_path: Path) -> None:
    script = tmp_path / "slow.py"
    script.write_text(
        "import time\nprint('slow-start', flush=True)\ntime.sleep(30)\nprint('slow-done', flush=True)\n",
        encoding="utf-8",
    )
    api = _StreamApi()
    api.status = "CANCEL_REQUESTED"
    _execute_claimed(api, tmp_path, _claimed("job-cancel", "slow.py"), 8000)
    assert api.finishes[0]["process_exited"] is True
    assert api.finishes[0]["timed_out"] is False
    assert all(text != "slow-done" for _, text in api.events)


def test_status_error_during_send_stops_the_process(tmp_path: Path) -> None:
    script = tmp_path / "sleep_job.py"
    script.write_text("import os, time\nprint('up', flush=True)\ntime.sleep(30)\n", encoding="utf-8")
    api = _StreamApi()
    _execute_claimed(api, tmp_path, _claimed("job-status-down", "sleep_job.py"), 8000)
    assert api.finishes[0]["termination_reason"] == REASON_SUPERVISION
    assert api.finishes[0]["process_exited"] is True
    assert any("상태 확인에 실패했습니다:" in text for _, text in api.events)


def test_output_limit_still_marked_when_streaming(tmp_path: Path) -> None:
    script = tmp_path / "talk.py"
    script.write_text("print('x' * 100)\nprint('y' * 100)\n", encoding="utf-8")
    api = _StreamApi()
    _execute_claimed(api, tmp_path, _claimed("job-limit", "talk.py"), 40)
    assert api.finishes[0]["output_truncated"] is True
    assert api.finishes[0]["termination_reason"] == REASON_OUTPUT_LIMIT
    assert any("OUTPUT_LIMIT_EXCEEDED" in text and "보관 줄 수 제한과는 별개" in text for _, text in api.events)
    assert all("출력 잘림" not in text for _, text in api.events)
