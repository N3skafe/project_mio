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


@dataclass(frozen=True)
class ParsedCommand:
    name: CommandName
    argument: str | None = None
    screen: ScreenId | None = None
    quiet: bool | None = None


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
    raise CommandSyntaxError(
        f"지원하지 않는 프로젝트 명령입니다: {sub}",
        "/project list",
    )


def _reject_extra(name: str, args: list[str]) -> None:
    if args:
        raise CommandSyntaxError(
            f"{name} 명령에는 추가 인자를 붙일 수 없습니다.",
            name,
        )
