"""테스트 공통 도우미."""

from __future__ import annotations

import time

from textual.pilot import Pilot
from textual.widgets import Input, RichLog

from maidops_tui.app import MaidOpsApp
from maidops_tui.config import AppConfig
from maidops_tui.domain.models import JobStatus


def make_config(**overrides: object) -> AppConfig:
    values: dict[str, object] = {
        "demo_delay_seconds": 0.05,
        "log_limit": 200,
        "character_name": "미오",
        "quiet": False,
    }
    values.update(overrides)
    return AppConfig(**values)  # type: ignore[arg-type]


def make_app(**overrides: object) -> MaidOpsApp:
    return MaidOpsApp(config=make_config(**overrides))


async def submit(pilot: Pilot[None], app: MaidOpsApp, text: str) -> None:
    seen = app.command_count
    box = app.query_one("#command-input", Input)
    box.focus()
    box.value = text
    await box.action_submit()
    await wait_for(
        pilot,
        lambda: app.command_count > seen,
        app=app,
        description="명령 처리",
    )


def rich_log_text(log: RichLog) -> str:
    return "\n".join(getattr(strip, "text", str(strip)) for strip in log.lines)


def app_state_text(app: MaidOpsApp) -> str:
    focused = app.focused.id if app.focused is not None and app.focused.id else "없음"
    screen = type(app.screen).__name__
    recent = list(app.activity_lines[-12:])
    return (
        f"screen={screen} focused={focused} command_count={app.command_count} "
        f"activity={recent!r}"
    )


async def wait_for(
    pilot: Pilot[None],
    predicate,
    timeout: float = 3.0,
    app: MaidOpsApp | None = None,
    description: str = "조건",
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await pilot.pause(0.05)
    detail = f" {app_state_text(app)}" if app is not None else ""
    raise AssertionError(f"{description} 완료를 {timeout:.1f}초 안에 확인하지 못했습니다.{detail}")


async def wait_for_terminal_jobs(pilot: Pilot[None], app: MaidOpsApp, timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        jobs = await app.service.list_jobs()
        if jobs and all(
            job.status not in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.CANCEL_REQUESTED} for job in jobs
        ):
            await pilot.pause()
            return jobs
        await pilot.pause(0.05)
    raise AssertionError(f"작업이 끝나지 않았습니다. {app_state_text(app)}")
