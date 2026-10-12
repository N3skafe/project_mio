"""명령 파서 테스트."""

from __future__ import annotations

import pytest

from maidops_tui.commands.help_text import COMMAND_EXAMPLES
from maidops_tui.commands.parser import CommandName, parse_command
from maidops_tui.domain.errors import CommandSyntaxError
from maidops_tui.domain.models import ScreenId


@pytest.mark.parametrize("example", [item[0] for item in COMMAND_EXAMPLES])
def test_documented_examples_parse(example: str) -> None:
    parsed = parse_command(example)
    assert isinstance(parsed.name, CommandName)


def test_project_select_keeps_id_case() -> None:
    parsed = parse_command("/project select demo-web")
    assert parsed.name is CommandName.PROJECT_SELECT
    assert parsed.argument == "demo-web"
    assert parsed.screen is ScreenId.WORKSPACE


@pytest.mark.parametrize(
    ("raw", "example"),
    [
        ("테스트 실행해", "/help"),
        ("/unknown", "/help"),
        ("/project", "/project list"),
        ("/project select", "/project select demo-api"),
        ("/project select demo-api extra", "/project select demo-api"),
        ("/cancel", "/cancel job-0001"),
        ("/quiet", "/quiet on"),
        ("/test now", "/test"),
        ("", "/help"),
    ],
)
def test_invalid_commands_include_example(raw: str, example: str) -> None:
    with pytest.raises(CommandSyntaxError) as caught:
        parse_command(raw)
    assert caught.value.example == example
    assert caught.value.message


def test_quiet_on_and_off() -> None:
    assert parse_command("/quiet ON").quiet is True
    assert parse_command("/QUIET off").quiet is False


def test_help_has_no_screen_change() -> None:
    assert parse_command("/help").screen is None
