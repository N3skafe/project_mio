"""대기 작업을 하나씩 claim해서 등록된 명령만 실행한다."""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from maidops_worker.client import WorkerApi
from maidops_worker.command import CommandRejected, resolve_command
from maidops_worker.masking import mask_secrets
from maidops_worker.runner import run_registered_process


def run_loop(
    *,
    base_url: str,
    workspace_root: Path,
    worker_id: str | None = None,
    once: bool = False,
    idle_seconds: float = 1.0,
    output_limit_bytes: int = 64_000,
) -> None:
    identity = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    api = WorkerApi(base_url, identity)
    alive = Path(os.environ.get("MAIDOPS_WORKER_ALIVE_FILE", "")) if os.environ.get("MAIDOPS_WORKER_ALIVE_FILE") else None
    try:
        while True:
            _touch(alive)
            api.heartbeat()
            claimed = api.claim()
            if claimed is None:
                if once:
                    return
                time.sleep(idle_seconds)
                continue
            _execute_claimed(api, workspace_root, claimed, output_limit_bytes)
            if once:
                return
    finally:
        api.close()


def _execute_claimed(api: WorkerApi, workspace_root: Path, claimed: dict, output_limit_bytes: int) -> None:
    job_id = str(claimed["job_id"])
    try:
        command = resolve_command(
            workspace_root,
            _relative_workdir(workspace_root, str(claimed["working_directory"])),
            list(claimed["argv"]),
        )
    except (CommandRejected, ValueError) as exc:
        api.append_events(job_id, [("SYSTEM", mask_secrets(exc.message))])
        api.finish(job_id, exit_code=None, process_exited=True, timed_out=False)
        return
    # The server already resolved the script to an absolute path. Accept that path
    # only after resolve_command checked the original relative argv. Here argv[0] is
    # still {python} and argv[1] may be absolute. Re-check it stays under the root.
    script = Path(command.argv[1])
    if not script.is_relative_to(workspace_root.resolve()):
        api.append_events(job_id, [("SYSTEM", "스크립트가 허용 경로 밖에 있습니다.")])
        api.finish(job_id, exit_code=None, process_exited=True, timed_out=False)
        return

    def should_cancel() -> bool:
        return api.job_status(job_id) == "CANCEL_REQUESTED"

    def heartbeat() -> None:
        api.heartbeat_job(job_id)

    result = run_registered_process(
        command.argv,
        str(command.working_directory),
        timeout_seconds=int(claimed["timeout_seconds"]),
        output_limit_bytes=output_limit_bytes,
        should_cancel=should_cancel,
        heartbeat=heartbeat,
    )
    api.append_events(job_id, [(line.stream, mask_secrets(line.text)) for line in result.lines])
    api.finish(
        job_id,
        exit_code=result.exit_code,
        process_exited=result.process_exited,
        timed_out=result.timed_out,
    )


def _relative_workdir(root: Path, working_directory: str) -> str:
    path = Path(working_directory)
    if path.is_absolute():
        return str(path.resolve().relative_to(root.resolve()))
    return working_directory


def _touch(path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(time.time()), encoding="utf-8")
