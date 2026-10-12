"""등록 명령의 실제 실행, 실패 로그, 취소, 경로 거부를 확인한다."""

from __future__ import annotations

from pathlib import Path

import pytest

from maidops_worker.command import CommandRejected, resolve_command
from maidops_worker.masking import mask_secrets
from maidops_worker.runner import run_registered_process

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "trusted-projects"


def test_rejects_shell_and_paths_outside_the_root() -> None:
    with pytest.raises(CommandRejected):
        resolve_command(ROOT, "sample", ["cmd.exe", "/c", "pass_check.py"])
    with pytest.raises(CommandRejected):
        resolve_command(ROOT, "..", ["{python}", "pass_check.py"])
    with pytest.raises(CommandRejected):
        resolve_command(ROOT, "sample", ["{python}", "pass_check.py && calc"])


def test_pass_and_fail_fixtures_keep_exit_codes_and_streams() -> None:
    passed = _run("pass_check.py", timeout_seconds=10)
    assert passed.process_exited is True
    assert passed.exit_code == 0
    assert any(line.stream == "STDOUT" and line.text == "check ok" for line in passed.lines)

    failed = _run("fail_check.py", timeout_seconds=10)
    assert failed.process_exited is True
    assert failed.exit_code == 2
    assert any(line.stream == "STDERR" and line.text == "boom" for line in failed.lines)


def test_cancel_stops_the_slow_fixture_process_tree() -> None:
    result = _run("slow_check.py", timeout_seconds=30, cancel_after_lines=1)
    assert result.process_exited is True
    assert result.timed_out is False
    assert any(line.text == "slow-start" for line in result.lines)
    assert all(line.text != "slow-done" for line in result.lines)


def test_masks_secret_assignments() -> None:
    assert mask_secrets("token=abc.def password = hunter2") == "token=[REDACTED] password = [REDACTED]"
    assert "secret-value" not in mask_secrets("Authorization Bearer secret-value")


def _run(script: str, *, timeout_seconds: int, cancel_after_lines: int = 0):
    command = resolve_command(ROOT, "sample", ["{python}", script])
    seen = {"count": 0}

    def should_cancel() -> bool:
        return cancel_after_lines > 0 and seen["count"] >= cancel_after_lines

    def heartbeat() -> None:
        seen["count"] += 1

    return run_registered_process(
        command.argv,
        str(command.working_directory),
        timeout_seconds=timeout_seconds,
        output_limit_bytes=8000,
        should_cancel=should_cancel,
        heartbeat=heartbeat,
        poll_seconds=0.05,
    )
