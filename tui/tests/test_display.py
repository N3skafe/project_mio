"""작업 표시가 출력 한도 중단과 로그 보관을 구분하는지 확인한다."""

from __future__ import annotations

from datetime import datetime, timezone

from maidops_tui.domain.display import format_job_meta
from maidops_tui.domain.models import Job, JobStatus


def _job(**overrides: object) -> Job:
    values: dict[str, object] = {
        "id": "job-0001",
        "project_id": "demo-api",
        "task_id": "api-db-check",
        "status": JobStatus.FAILED,
        "created_at": datetime(2026, 10, 13, tzinfo=timezone.utc),
        "started_at": datetime(2026, 10, 13, tzinfo=timezone.utc),
        "finished_at": datetime(2026, 10, 13, tzinfo=timezone.utc),
        "cancel_requested_at": None,
    }
    values.update(overrides)
    return Job(**values)  # type: ignore[arg-type]


def test_output_limit_reason_is_not_the_retained_log_label() -> None:
    now = datetime(2026, 10, 13, 0, 0, 1, tzinfo=timezone.utc)
    stopped = format_job_meta(
        _job(output_truncated=True, termination_reason="OUTPUT_LIMIT_EXCEEDED"),
        now,
    )
    assert "FAIL" in stopped
    assert "OUTPUT_LIMIT_EXCEEDED" in stopped
    assert "출력 잘림" not in stopped

    retained = format_job_meta(
        _job(status=JobStatus.SUCCEEDED, output_truncated=True, termination_reason="COMPLETED"),
        now,
    )
    assert "PASS" in retained
    assert "출력 잘림" in retained
    assert "OUTPUT_LIMIT_EXCEEDED" not in retained
