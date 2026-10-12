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
    lines: tuple[OutputChunk, ...]


def run_registered_process(
    argv: tuple[str, ...],
    working_directory: str,
    *,
    timeout_seconds: int,
    output_limit_bytes: int,
    should_cancel: Callable[[], bool],
    heartbeat: Callable[[], None],
    poll_seconds: float = 0.2,
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
    lines: queue.Queue[OutputChunk] = queue.Queue()
    threads = [
        threading.Thread(target=_read_stream, args=(process.stdout, "STDOUT", lines), daemon=True),
        threading.Thread(target=_read_stream, args=(process.stderr, "STDERR", lines), daemon=True),
    ]
    for thread in threads:
        thread.start()
    started = time.monotonic()
    timed_out = False
    truncated = False
    collected: list[OutputChunk] = []
    while process.poll() is None:
        truncated = _drain(lines, collected, output_limit_bytes) or truncated
        if should_cancel() or truncated or time.monotonic() - started > timeout_seconds:
            timed_out = not should_cancel() and not truncated and time.monotonic() - started > timeout_seconds
            terminate_process_tree(process.pid)
            break
        heartbeat()
        time.sleep(poll_seconds)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _join_and_drain(threads, lines, collected, output_limit_bytes)
            return ProcessResult(process.returncode, False, timed_out, truncated, tuple(collected))
    truncated = _join_and_drain(threads, lines, collected, output_limit_bytes) or truncated
    return ProcessResult(
        exit_code=process.returncode,
        process_exited=process.poll() is not None,
        timed_out=timed_out,
        output_truncated=truncated,
        lines=tuple(collected),
    )


def _read_stream(pipe, stream: str, lines: queue.Queue[OutputChunk]) -> None:
    if pipe is None:
        return
    for line in pipe:
        lines.put(OutputChunk(stream, line.rstrip("\r\n")))
    pipe.close()


def _drain(lines: queue.Queue[OutputChunk], collected: list[OutputChunk], output_limit_bytes: int) -> bool:
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
    return truncated


def _join_and_drain(threads, lines, collected, output_limit_bytes: int) -> bool:
    for thread in threads:
        thread.join(timeout=1)
    return _drain(lines, collected, output_limit_bytes)
