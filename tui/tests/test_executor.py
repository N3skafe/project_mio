"""명령 실행기 테스트."""

from __future__ import annotations

from maidops_tui.commands.executor import run_command_text
from maidops_tui.domain.models import ConnectionStatus, ScreenId
from maidops_tui.services.demo_service import DemoService
from tests.test_demo_service import _disconnected_service


async def test_natural_language_does_not_start_a_job() -> None:
    service = DemoService(delay_seconds=0.05, log_limit=20)
    try:
        result = await run_command_text(service, "테스트 실행해 줘")
        assert result.ok is False
        assert result.lines[0].startswith("오류:")
        assert any(line.startswith("예:") for line in result.lines)
        assert await service.list_jobs() == []
    finally:
        await service.aclose()


async def test_unknown_command_does_not_raise() -> None:
    service = DemoService(delay_seconds=0.05, log_limit=20)
    try:
        result = await run_command_text(service, "/dance")
        assert result.ok is False
        assert "지원하지 않는 명령" in result.lines[0]
    finally:
        await service.aclose()


async def test_help_lists_commands() -> None:
    service = DemoService(delay_seconds=0.05, log_limit=20)
    try:
        result = await run_command_text(service, "/help")
        text = "\n".join(result.lines)
        assert result.ok is True
        for token in ("/project list", "/cancel", "/quiet on", "/lab"):
            assert token in text
    finally:
        await service.aclose()


async def test_live_test_command_reports_connection_failure() -> None:
    service = _disconnected_service()
    try:
        result = await run_command_text(service, "/test")
        assert result.ok is False
        assert "백엔드에 연결하지 못했습니다" in result.lines[0]
        assert "성공으로 처리하지 않습니다" in result.lines[0]
        assert result.screen is ScreenId.WORKSPACE
        assert service.connection_status() is ConnectionStatus.DISCONNECTED
    finally:
        await service.aclose()
