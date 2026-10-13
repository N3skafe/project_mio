"""등록된 argv를 shell=False로 실행하고 stdout/stderr 도착 순서를 유지한다."""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from maidops_worker.process_tree import terminate_process_tree

REASON_COMPLETED = "COMPLETED"
REASON_FAILED = "FAILED"
REASON_TIMED_OUT = "TIMED_OUT"
REASON_OUTPUT_LIMIT = "OUTPUT_LIMIT_EXCEEDED"
REASON_SUPERVISION = "SUPERVISION_FAILED"
STAGE_STATUS = "status"
STAGE_HEARTBEAT = "heartbeat"
STAGE_OUTPUT = "output"


@dataclass(frozen=True)
class OutputChunk:
    stream: str
    text: str


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int | None
    process_exited: bool
    timed_out: bool
    output_truncated: bool
    termination_reason: str
    lines: tuple[OutputChunk, ...]
    supervision_stage: str | None = None
    supervision_error: str | None = None
    cleanup_error: str | None = None


def run_registered_process(
    argv: tuple[str, ...],
    working_directory: str,
    *,
    timeout_seconds: int,
    output_limit_bytes: int,
    should_cancel: Callable[[], bool],
    heartbeat: Callable[[], None],
    poll_seconds: float = 0.2,
    on_line: Callable[[str, str], None] | None = None,
) -> ProcessResult:
    popen_kwargs: dict[str, object] = {
        "args": list(argv),
        "cwd": working_directory,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "stdin": subprocess.DEVNULL,
        "shell": False,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(**popen_kwargs)
    read_errors: list[BaseException] = []
    lines: queue.Queue[OutputChunk] = queue.Queue()
    threads = [
        threading.Thread(
            target=_read_stream,
            args=(process.stdout, "STDOUT", lines, read_errors),
            daemon=True,
        ),
        threading.Thread(
            target=_read_stream,
            args=(process.stderr, "STDERR", lines, read_errors),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()
    started = time.monotonic()
    timed_out = False
    truncated = False
    collected: list[OutputChunk] = []
    supervision: BaseException | None = None
    stage: str | None = None
    cleanup_error: str | None = None
    stop: str | None = None
    try:
        while process.poll() is None:
            try:
                truncated = _drain(lines, collected, output_limit_bytes, on_line) or truncated
            except Exception as exc:
                supervision = exc
                stage = STAGE_OUTPUT
                break
            if read_errors:
                supervision = read_errors[0]
                stage = STAGE_OUTPUT
                break
            try:
                cancel = bool(should_cancel())
            except Exception as exc:
                supervision = exc
                stage = STAGE_STATUS
                break
            if cancel or truncated or time.monotonic() - started > timeout_seconds:
                if cancel:
                    stop = "cancel"
                elif truncated:
                    stop = "limit"
                else:
                    stop = "timeout"
                    timed_out = True
                break
            try:
                heartbeat()
            except Exception as exc:
                supervision = exc
                stage = STAGE_HEARTBEAT
                break
            time.sleep(poll_seconds)
    finally:
        if process.poll() is None:
            cleanup_error = _stop_and_confirm(process)
        try:
            truncated = _join_and_drain(threads, lines, collected, output_limit_bytes, on_line) or truncated
        except Exception as exc:
            if supervision is None:
                supervision = exc
                stage = STAGE_OUTPUT
        if read_errors and supervision is None:
            supervision = read_errors[0]
            stage = STAGE_OUTPUT
        if process.poll() is None and cleanup_error is None:
            cleanup_error = "프로세스 종료를 확인하지 못했습니다."
    exited = process.poll() is not None
    result = ProcessResult(
        exit_code=process.returncode,
        process_exited=exited,
        timed_out=timed_out and supervision is None,
        output_truncated=truncated,
        termination_reason=_termination_reason(
            supervision=supervision is not None,
            stop=stop,
            truncated=truncated,
            timed_out=timed_out and supervision is None,
            process_exited=exited,
            exit_code=process.returncode,
        ),
        lines=tuple(collected),
        supervision_stage=stage,
        supervision_error=None if supervision is None else str(supervision),
        cleanup_error=None if exited else cleanup_error,
    )
    if supervision is not None:
        setattr(supervision, "process_result", result)
        raise supervision
    return result


def _termination_reason(
    *,
    supervision: bool,
    stop: str | None,
    truncated: bool,
    timed_out: bool,
    process_exited: bool,
    exit_code: int | None,
) -> str:
    if supervision or not process_exited:
        return REASON_SUPERVISION
    if stop == "limit" or (stop is None and truncated):
        return REASON_OUTPUT_LIMIT
    if stop == "timeout" or timed_out:
        return REASON_TIMED_OUT
    if exit_code == 0:
        return REASON_COMPLETED
    return REASON_FAILED


def _stop_and_confirm(process: subprocess.Popen[str]) -> str | None:
    """프로세스가 끝났으면 None, 끝나지 않았으면 정리 실패 문구를 반환한다."""

    if process.poll() is not None:
        return None
    call_error: str | None = None
    try:
        terminate_process_tree(process.pid)
    except Exception as exc:
        call_error = f"프로세스 트리 정리 호출에 실패했습니다: {exc}"
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=2)
        except Exception as exc:
            detail = f"프로세스 종료를 확인하지 못했습니다: {exc}"
            return _join_cleanup(call_error, detail)
    if process.poll() is None:
        return _join_cleanup(call_error, "프로세스 종료를 확인하지 못했습니다.")
    return None


def _join_cleanup(call_error: str | None, detail: str) -> str:
    if call_error is None:
        return detail
    return f"{call_error} {detail}"


def _read_stream(
    pipe,
    stream: str,
    lines: queue.Queue[OutputChunk],
    errors: list[BaseException],
) -> None:
    if pipe is None:
        return
    try:
        for line in pipe:
            lines.put(OutputChunk(stream, line.rstrip("\r\n")))
        pipe.close()
    except Exception as exc:
        errors.append(exc)


def _drain(
    lines: queue.Queue[OutputChunk],
    collected: list[OutputChunk],
    output_limit_bytes: int,
    on_line: Callable[[str, str], None] | None = None,
) -> bool:
    truncated = False
    while True:
        try:
            item = lines.get_nowait()
        except queue.Empty:
            return truncated
        if item.text == "":
            continue
        size = sum(len(chunk.text.encode("utf-8", errors="replace")) for chunk in collected)
        if size + len(item.text.encode("utf-8", errors="replace")) > output_limit_bytes:
            truncated = True
            continue
        collected.append(item)
        if on_line is not None:
            on_line(item.stream, item.text)
    return truncated


def _join_and_drain(threads, lines, collected, output_limit_bytes: int, on_line=None) -> bool:
    for thread in threads:
        thread.join(timeout=1)
    return _drain(lines, collected, output_limit_bytes, on_line)
