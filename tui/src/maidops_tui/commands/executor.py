"""파싱된 명령을 서비스 호출로 실행한다. 위젯을 직접 다루지 않는다."""

from __future__ import annotations

from dataclasses import dataclass

from maidops_tui.commands.help_text import help_lines
from maidops_tui.commands.parser import CommandName, ParsedCommand, parse_command
from maidops_tui.domain.display import display_status, format_elapsed
from maidops_tui.domain.errors import LabError, format_lab_error
from maidops_tui.domain.models import JobStatus, ScreenId
from maidops_tui.services.protocol import LabService


@dataclass(frozen=True)
class CommandResult:
    ok: bool
    lines: tuple[str, ...]
    screen: ScreenId | None = None
    quiet: bool | None = None


async def run_command_text(service: LabService, raw: str) -> CommandResult:
    try:
        parsed = parse_command(raw)
    except LabError as exc:
        return CommandResult(False, tuple(format_lab_error(exc)))
    return await execute_command(service, parsed)


async def execute_command(service: LabService, command: ParsedCommand) -> CommandResult:
    try:
        return await _execute(service, command)
    except LabError as exc:
        return CommandResult(False, tuple(format_lab_error(exc)), screen=command.screen)


async def _execute(service: LabService, command: ParsedCommand) -> CommandResult:
    if command.name is CommandName.HELP:
        return CommandResult(True, tuple(help_lines()))
    if command.name is CommandName.QUIET_ON:
        return CommandResult(True, ("조용한 모드를 켰습니다. 대사만 숨기고 상태는 유지합니다.",), quiet=True)
    if command.name is CommandName.QUIET_OFF:
        return CommandResult(True, ("조용한 모드를 껐습니다.",), quiet=False)
    if command.name is CommandName.REVIEW:
        return CommandResult(True, ("Review 화면입니다. 이번 세션의 오류 사례를 검토합니다.",), screen=ScreenId.REVIEW)
    if command.name is CommandName.LAB:
        return CommandResult(
            True,
            ("Lab 화면입니다. DEMO에서는 학습하지 않습니다. LIVE는 확정 라벨이 조건을 만족할 때만 학습합니다.",),
            screen=ScreenId.LAB,
        )
    if command.name is CommandName.HISTORY:
        return CommandResult(
            True,
            ("History 화면입니다. 키워드 검색은 이번 세션과 가상 fixture를 구분해서 보여 줍니다.",),
            screen=ScreenId.HISTORY,
        )
    if command.name is CommandName.PROJECT_LIST:
        return CommandResult(True, tuple(await _project_lines(service)), screen=ScreenId.WORKSPACE)
    if command.name is CommandName.PROJECT_SELECT:
        assert command.argument is not None
        project = await service.select_project(command.argument)
        return CommandResult(
            True,
            (f"프로젝트를 선택했습니다: {project.id} {project.name}",),
            screen=ScreenId.WORKSPACE,
        )
    if command.name is CommandName.TEST:
        job = await service.create_test_job()
        if job.status is JobStatus.QUEUED:
            lines = (
                f"작업을 저장했습니다: {job.id}",
                "실행 워커가 없어 QUEUED로 남습니다. 성공이나 실패로 처리하지 않습니다.",
                f"상태: {display_status(job.status)}",
            )
        else:
            lines = (
                f"가상 작업을 시작했습니다: {job.id}",
                "DEMO 이벤트입니다. 실제 테스트 프로세스는 실행하지 않습니다.",
                f"상태: {display_status(job.status)}",
            )
        return CommandResult(True, lines, screen=ScreenId.WORKSPACE)
    if command.name is CommandName.JOBS:
        return CommandResult(True, tuple(await _job_lines(service)), screen=ScreenId.WORKSPACE)
    if command.name is CommandName.CANCEL:
        assert command.argument is not None
        job = await service.cancel_job(command.argument)
        return CommandResult(
            True,
            (
                f"작업을 취소했습니다: {job.id}",
                f"상태: {display_status(job.status)}",
                "늦은 가상 완료 이벤트는 이 작업을 성공으로 바꾸지 않습니다.",
            ),
            screen=ScreenId.WORKSPACE,
        )
    raise AssertionError(f"unhandled command: {command.name}")


async def _project_lines(service: LabService) -> list[str]:
    projects = await service.list_projects()
    selected = await service.get_selected_project()
    lines = ["등록 프로젝트 (가상 fixture):"]
    for project in projects:
        mark = "선택" if selected is not None and selected.id == project.id else "-"
        lines.append(f"{mark}  {project.id}  {project.name}  {project.summary}")
    return lines


async def _job_lines(service: LabService) -> list[str]:
    jobs = await service.list_jobs()
    if not jobs:
        return ["이번 세션에 작업이 없습니다.", "예: /test"]
    lines = ["이번 세션 작업:"]
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    for job in jobs:
        lines.append(
            f"{job.id}  {display_status(job.status)}  "
            f"{format_elapsed(job.elapsed_seconds(now))}  "
            f"project={job.project_id} task={job.task_id}"
        )
    return lines
