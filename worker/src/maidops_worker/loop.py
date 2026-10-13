"""대기 작업을 하나씩 claim해서 등록된 명령만 실행한다."""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from maidops_worker.client import WorkerApi
from maidops_worker.command import CommandRejected, resolve_command
from maidops_worker.log_shipper import LogShipper
from maidops_worker.masking import mask_secrets
from maidops_worker.runner import (
    REASON_FAILED,
    REASON_OUTPUT_LIMIT,
    REASON_SUPERVISION,
    STAGE_HEARTBEAT,
    STAGE_OUTPUT,
    STAGE_STATUS,
    ProcessResult,
    run_registered_process,
)

_STAGE_LABEL = {
    STAGE_STATUS: "상태 확인에 실패했습니다",
    STAGE_HEARTBEAT: "하트비트에 실패했습니다",
    STAGE_OUTPUT: "출력 처리에 실패했습니다",
}
_OUTPUT_LIMIT_LINE = (
    "OUTPUT_LIMIT_EXCEEDED. 출력 한도로 프로세스를 중단했습니다. "
    "보관 줄 수 제한과는 별개입니다."
)


def run_loop(
    *,
    base_url: str,
    workspace_root: Path,
    worker_id: str | None = None,
    once: bool = False,
    idle_seconds: float = 1.0,
    output_limit_bytes: int = 64_000,
    api: WorkerApi | None = None,
    stop_on_empty: bool = False,
) -> None:
    owns_api = api is None
    if api is None:
        identity = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        api = WorkerApi(base_url, identity)
    alive = Path(os.environ.get("MAIDOPS_WORKER_ALIVE_FILE", "")) if os.environ.get("MAIDOPS_WORKER_ALIVE_FILE") else None
    try:
        while True:
            _touch(alive)
            try:
                api.heartbeat()
                claimed = api.claim()
            except Exception:
                if once:
                    raise
                time.sleep(idle_seconds)
                continue
            if claimed is None:
                if once or stop_on_empty:
                    return
                time.sleep(idle_seconds)
                continue
            try:
                _execute_claimed(api, workspace_root, claimed, output_limit_bytes)
            except Exception as exc:
                print(f"작업 처리 중 예외가 났습니다. 다음 작업을 계속합니다: {exc}", file=sys.stderr)
            if once:
                return
    finally:
        if owns_api:
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
        _deliver(
            api,
            job_id,
            [("SYSTEM", mask_secrets(str(exc)))],
            _failure_kwargs(exit_code=None, process_exited=True, output_truncated=False, reason=REASON_FAILED),
        )
        return
    script = Path(command.argv[1])
    if not script.is_relative_to(workspace_root.resolve()):
        _deliver(
            api,
            job_id,
            [("SYSTEM", "스크립트가 허용 경로 밖에 있습니다.")],
            _failure_kwargs(exit_code=None, process_exited=True, output_truncated=False, reason=REASON_FAILED),
        )
        return

    def should_cancel() -> bool:
        return api.job_status(job_id) == "CANCEL_REQUESTED"

    def heartbeat() -> None:
        accepted = api.heartbeat_job(job_id)
        if accepted is False:
            raise RuntimeError("하트비트가 거절되었습니다.")

    shipper = LogShipper(api, job_id)
    shipper.start()
    try:
        result = run_registered_process(
            command.argv,
            str(command.working_directory),
            timeout_seconds=int(claimed["timeout_seconds"]),
            output_limit_bytes=output_limit_bytes,
            should_cancel=should_cancel,
            heartbeat=heartbeat,
            on_line=shipper.offer,
        )
    except Exception as exc:
        result = getattr(exc, "process_result", None)
        _report_supervision(api, job_id, exc, result if isinstance(result, ProcessResult) else None, shipper)
        return
    _report_result(api, job_id, result, shipper)


def _report_result(api: WorkerApi, job_id: str, result: ProcessResult, shipper: LogShipper) -> None:
    if result.supervision_error is not None or not result.process_exited:
        _report_supervision(
            api,
            job_id,
            RuntimeError(result.supervision_error or result.cleanup_error or ""),
            result,
            shipper,
        )
        return
    if result.termination_reason == REASON_OUTPUT_LIMIT:
        shipper.offer("SYSTEM", _OUTPUT_LIMIT_LINE)
    incomplete = not shipper.close(2.0)
    _deliver(
        api,
        job_id,
        [],
        {
            "exit_code": result.exit_code,
            "process_exited": result.process_exited,
            "timed_out": result.timed_out,
            "output_truncated": result.output_truncated,
            "termination_reason": result.termination_reason,
            "log_storage_incomplete": incomplete,
        },
    )


def _report_supervision(
    api: WorkerApi,
    job_id: str,
    exc: BaseException,
    result: ProcessResult | None,
    shipper: LogShipper | None = None,
) -> None:
    stage = result.supervision_stage if result is not None and result.supervision_stage else STAGE_STATUS
    label = _STAGE_LABEL.get(stage, _STAGE_LABEL[STAGE_STATUS])
    notices: list[tuple[str, str]] = []
    if result is not None and result.supervision_error:
        notices.append(("SYSTEM", mask_secrets(f"{label}: {result.supervision_error}")))
    elif result is None or not result.cleanup_error:
        notices.append(("SYSTEM", mask_secrets(f"{label}: {exc}")))
    if result is not None and result.cleanup_error:
        notices.append(("SYSTEM", mask_secrets(result.cleanup_error)))
    incomplete = False
    if shipper is not None:
        for stream, text in notices:
            shipper.offer(stream, text)
        incomplete = not shipper.close(2.0)
    else:
        _deliver(
            api,
            job_id,
            notices,
            _failure_kwargs(
                exit_code=None if result is None else result.exit_code,
                process_exited=bool(result and result.process_exited),
                output_truncated=bool(result and result.output_truncated),
                reason=REASON_SUPERVISION,
            ),
        )
        return
    _deliver(
        api,
        job_id,
        [],
        _failure_kwargs(
            exit_code=None if result is None else result.exit_code,
            process_exited=bool(result and result.process_exited),
            output_truncated=bool(result and result.output_truncated),
            reason=REASON_SUPERVISION,
            log_storage_incomplete=incomplete,
        ),
    )


def _failure_kwargs(
    *,
    exit_code: int | None,
    process_exited: bool,
    output_truncated: bool,
    reason: str,
    log_storage_incomplete: bool = False,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "process_exited": process_exited,
        "timed_out": False,
        "output_truncated": output_truncated,
        "termination_reason": reason,
        "log_storage_incomplete": log_storage_incomplete,
    }


def _deliver(api: WorkerApi, job_id: str, events: list[tuple[str, str]], finish_kwargs: dict[str, Any]) -> None:
    """실패 보고가 거절되어도 성공 finish로 다시 호출하지 않는다."""

    payload = dict(finish_kwargs)
    try:
        if events:
            api.append_events(job_id, [(stream, mask_secrets(text)) for stream, text in events])
    except Exception:
        payload["log_storage_incomplete"] = True
    try:
        api.finish(job_id, **payload)
    except Exception:
        return


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
