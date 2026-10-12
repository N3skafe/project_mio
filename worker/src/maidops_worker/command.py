"""등록된 argv만 허용한다. 셸 문자열은 만들지 않는다."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


class CommandRejected(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class ResolvedCommand:
    argv: tuple[str, ...]
    working_directory: Path


def resolve_command(workspace_root: Path, relative_workdir: str, argv: list[str]) -> ResolvedCommand:
    root = workspace_root.resolve()
    if not root.is_dir():
        raise CommandRejected(f"허용된 작업 디렉터리가 없습니다: {root}")
    relative = Path(relative_workdir)
    if relative.is_absolute() or any(part == ".." for part in relative.parts):
        raise CommandRejected("작업 디렉터리가 허용 경로 밖입니다.")
    workdir = (root / relative).resolve()
    if not workdir.is_relative_to(root) or not workdir.is_dir():
        raise CommandRejected(f"작업 디렉터리를 찾지 못했습니다: {workdir}")
    if not 2 <= len(argv) <= 8:
        raise CommandRejected("argv 길이가 허용 범위가 아닙니다.")
    if argv[0] != "{python}":
        raise CommandRejected("실행 파일은 {python} 토큰만 허용합니다.")
    resolved: list[str] = [sys.executable]
    for index, arg in enumerate(argv):
        if not isinstance(arg, str) or arg.strip() == "" or "\n" in arg or "\x00" in arg:
            raise CommandRejected("argv에 빈 값이나 제어 문자가 있습니다.")
        if any(token in arg for token in ("&&", "||", "|", ">", "<")):
            raise CommandRejected("argv에 셸 연산자가 있습니다.")
        if index == 0:
            continue
        if index == 1:
            script = (workdir / arg).resolve()
            if not script.is_relative_to(root) or not script.is_file():
                raise CommandRejected(f"스크립트가 허용 경로 안에 없습니다: {arg}")
            resolved.append(str(script))
        else:
            resolved.append(arg)
    return ResolvedCommand(argv=tuple(resolved), working_directory=workdir)
