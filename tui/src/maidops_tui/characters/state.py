"""캐릭터 상태는 서비스 사실에서만 계산한다.

학습 완료와 평가 점수는 연구실 상태가 실제로 그럴 때만 TRAINING, REPORTING이 된다.
라벨 승인만으로는 그 상태로 바뀌지 않는다.
"""

from __future__ import annotations

from collections.abc import Sequence

from maidops_tui.domain.models import (
    CharacterState,
    ConnectionStatus,
    DataOrigin,
    ErrorCase,
    Job,
    JobStatus,
    LabStatus,
    ReviewStatus,
)


def derive_character_state(
    *,
    connection: ConnectionStatus,
    jobs: Sequence[Job],
    error_cases: Sequence[ErrorCase],
    lab: LabStatus | None = None,
) -> CharacterState:
    if connection is ConnectionStatus.DISCONNECTED:
        return CharacterState.DISCONNECTED
    if lab is not None and lab.active_run_status == "RUNNING":
        return CharacterState.TRAINING
    if any(job.status in {JobStatus.RUNNING, JobStatus.CANCEL_REQUESTED} for job in jobs):
        return CharacterState.WORKING
    session_cases = [case for case in error_cases if case.origin is DataOrigin.SESSION]
    if any(case.review_status is ReviewStatus.DRAFT and case.draft_label is not None for case in session_cases):
        return CharacterState.NEEDS_REVIEW
    if lab is not None and lab.awaiting_model_choice():
        return CharacterState.REPORTING
    if jobs:
        latest = max(jobs, key=lambda job: (job.created_at, job.id))
        if latest.status is JobStatus.FAILED:
            return CharacterState.FAILED
    return CharacterState.IDLE
