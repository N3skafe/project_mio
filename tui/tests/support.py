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
    box = app.query_one("#command-input", Input)
    box.focus()
    box.value = text
    await box.action_submit()
    await pilot.pause()


def rich_log_text(log: RichLog) -> str:
    return "\n".join(getattr(strip, "text", str(strip)) for strip in log.lines)


async def wait_for(pilot: Pilot[None], predicate, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await pilot.pause(0.05)
    raise AssertionError("조건이 제한 시간 안에 충족되지 않았습니다.")


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
    raise AssertionError(f"작업이 끝나지 않았습니다: {app.activity_lines}")
