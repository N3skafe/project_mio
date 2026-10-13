"""RUNNING 중 로그가 늘어나도 포커스와 기존 줄이 유지되는지 확인한다."""

from __future__ import annotations

from datetime import datetime, timezone

from textual.widgets import Input

from maidops_tui.domain.models import Job, JobStatus, OutputLine
from maidops_tui.screens.workspace import WorkspaceView
from tests.support import make_app, rich_log_text


def _running_job() -> Job:
    return Job(
        id="job-live",
        project_id="demo-api",
        task_id="api-db-check",
        status=JobStatus.RUNNING,
        created_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
        started_at=datetime(2026, 10, 13, tzinfo=timezone.utc),
        finished_at=None,
        cancel_requested_at=None,
    )


async def test_running_log_appends_without_stealing_focus_or_duplicating() -> None:
    app = make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        app.query_one("#command-input", Input).focus()
        view = app.query_one(WorkspaceView)
        job = _running_job()
        view.apply_jobs([job])
        view.apply_output(job, [OutputLine(sequence=1, text="first line")])
        await pilot.pause()
        assert app.focused is not None
        assert app.focused.id == "command-input"
        view.apply_output(
            job,
            [
                OutputLine(sequence=1, text="first line"),
                OutputLine(sequence=2, text="second line"),
            ],
        )
        await pilot.pause()
        log = rich_log_text(app.query_one("#job-log"))
        assert log.count("first line") == 1
        assert "second line" in log
        assert app.focused.id == "command-input"
        failed = Job(
            id=job.id,
            project_id=job.project_id,
            task_id=job.task_id,
            status=JobStatus.FAILED,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.created_at,
            cancel_requested_at=None,
            output_truncated=True,
            termination_reason="OUTPUT_LIMIT_EXCEEDED",
        )
        view.apply_jobs([failed])
        view.apply_output(
            failed,
            [
                OutputLine(sequence=1, text="first line"),
                OutputLine(sequence=2, text="second line"),
                OutputLine(sequence=3, text="RESULT FAIL exit_code=0 OUTPUT_LIMIT_EXCEEDED"),
            ],
        )
        await pilot.pause()
        assert "OUTPUT_LIMIT_EXCEEDED" in rich_log_text(app.query_one("#job-log"))
        assert "OUTPUT_LIMIT_EXCEEDED" in str(app.query_one("#job-meta").content)
        assert "출력 잘림" not in str(app.query_one("#job-meta").content)
