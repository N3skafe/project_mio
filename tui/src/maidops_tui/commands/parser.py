"""슬래시 명령을 구조화된 값으로 바꾼다. 화면 코드를 호출하지 않는다."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from maidops_tui.domain.errors import CommandSyntaxError
from maidops_tui.domain.models import ScreenId


class CommandName(StrEnum):
    HELP = "help"
    PROJECT_LIST = "project_list"
    PROJECT_SELECT = "project_select"
    TEST = "test"
    JOBS = "jobs"
    CANCEL = "cancel"
    REVIEW = "review"
    LAB = "lab"
    HISTORY = "history"
    QUIET_ON = "quiet_on"
    QUIET_OFF = "quiet_off"
    PROJECT_ADD = "project_add"
    TASK_ADD = "task_add"
    IMPORT_LOG = "import_log"
    SIMILAR = "similar"
    ADVISE = "advise"


@dataclass(frozen=True)
class ParsedCommand:
    name: CommandName
    argument: str | None = None
    screen: ScreenId | None = None
    quiet: bool | None = None
    extra: tuple[str, ...] = ()


def parse_command(raw: str) -> ParsedCommand:
    text = raw.strip()
    if not text:
        raise CommandSyntaxError("명령이 비어 있습니다.", "/help")
    if not text.startswith("/"):
        raise CommandSyntaxError(
            "명시적 명령만 지원합니다. 자연어는 해석하지 않습니다.",
            "/help",
        )
    parts = text.split()
    head = parts[0].lower()
    args = parts[1:]

    if head == "/help":
        _reject_extra("/help", args)
        return ParsedCommand(CommandName.HELP)
    if head == "/test":
        _reject_extra("/test", args)
        return ParsedCommand(CommandName.TEST, screen=ScreenId.WORKSPACE)
    if head == "/jobs":
        _reject_extra("/jobs", args)
        return ParsedCommand(CommandName.JOBS, screen=ScreenId.WORKSPACE)
    if head == "/review":
        _reject_extra("/review", args)
        return ParsedCommand(CommandName.REVIEW, screen=ScreenId.REVIEW)
    if head == "/lab":
        _reject_extra("/lab", args)
        return ParsedCommand(CommandName.LAB, screen=ScreenId.LAB)
    if head == "/history":
        _reject_extra("/history", args)
        return ParsedCommand(CommandName.HISTORY, screen=ScreenId.HISTORY)
    if head == "/cancel":
        if len(args) != 1:
            raise CommandSyntaxError("취소할 작업 id가 필요합니다.", "/cancel job-0001")
        return ParsedCommand(CommandName.CANCEL, argument=args[0], screen=ScreenId.WORKSPACE)
    if head == "/quiet":
        if len(args) != 1 or args[0].lower() not in {"on", "off"}:
            raise CommandSyntaxError("조용한 모드는 on 또는 off입니다.", "/quiet on")
        enabled = args[0].lower() == "on"
        return ParsedCommand(
            CommandName.QUIET_ON if enabled else CommandName.QUIET_OFF,
            quiet=enabled,
        )
    if head == "/project":
        return _parse_project(args)
    if head == "/task":
        return _parse_task(args)
    if head == "/import-log":
        return _parse_import(args)
    if head == "/similar":
        if not args:
            raise CommandSyntaxError(
                "비교할 실패 로그가 필요합니다.",
                "/similar Connection to localhost:5432 refused",
            )
        return ParsedCommand(CommandName.SIMILAR, extra=tuple(args), screen=ScreenId.REVIEW)
    if head == "/advise":
        if len(args) != 1:
            raise CommandSyntaxError("오류 사례 id가 필요합니다.", "/advise case-0001")
        return ParsedCommand(CommandName.ADVISE, argument=args[0], screen=ScreenId.REVIEW)
    raise CommandSyntaxError(f"지원하지 않는 명령입니다: {head}", "/help")


def _parse_project(args: list[str]) -> ParsedCommand:
    if not args:
        raise CommandSyntaxError("프로젝트 하위 명령이 필요합니다.", "/project list")
    sub = args[0].lower()
    rest = args[1:]
    if sub == "list":
        _reject_extra("/project list", rest)
        return ParsedCommand(CommandName.PROJECT_LIST, screen=ScreenId.WORKSPACE)
    if sub == "select":
        if len(rest) != 1:
            raise CommandSyntaxError("프로젝트 id가 필요합니다.", "/project select demo-api")
        return ParsedCommand(
            CommandName.PROJECT_SELECT,
            argument=rest[0],
            screen=ScreenId.WORKSPACE,
        )
    if sub == "add":
        if len(rest) < 2:
            raise CommandSyntaxError("프로젝트 id와 이름이 필요합니다.", "/project add my-api 내 API")
        return ParsedCommand(
            CommandName.PROJECT_ADD,
            argument=rest[0],
            extra=tuple(rest[1:]),
            screen=ScreenId.WORKSPACE,
        )
    raise CommandSyntaxError(
        f"지원하지 않는 프로젝트 명령입니다: {sub}",
        "/project list",
    )


def _parse_task(args: list[str]) -> ParsedCommand:
    if not args or args[0].lower() != "add":
        raise CommandSyntaxError("작업 하위 명령은 add입니다.", "/task add my-check sample pass_check.py 10 통과 점검")
    rest = args[1:]
    if len(rest) < 5:
        raise CommandSyntaxError(
            "작업 id, 상대 경로, 스크립트, 제한 시간, 이름이 필요합니다.",
            "/task add my-check sample pass_check.py 10 통과 점검",
        )
    if not rest[3].isdigit() or not 1 <= int(rest[3]) <= 120:
        raise CommandSyntaxError("timeout_seconds는 1 이상 120 이하여야 합니다.", "10")
    return ParsedCommand(
        CommandName.TASK_ADD,
        argument=rest[0],
        extra=tuple(rest[1:]),
        screen=ScreenId.WORKSPACE,
    )


def _parse_import(args: list[str]) -> ParsedCommand:
    if len(args) < 2:
        raise CommandSyntaxError(
            "프로젝트 id와 실패 로그가 필요합니다. 여러 줄은 Workspace의 가져오기 폼을 사용하세요.",
            "/import-log trusted-sample Connection to localhost:5432 refused",
        )
    return ParsedCommand(
        CommandName.IMPORT_LOG,
        argument=args[0],
        extra=tuple(args[1:]),
        screen=ScreenId.REVIEW,
    )


def _reject_extra(name: str, args: list[str]) -> None:
    if args:
        raise CommandSyntaxError(
            f"{name} 명령에는 추가 인자를 붙일 수 없습니다.",
            name,
        )
