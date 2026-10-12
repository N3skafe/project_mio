"""캐릭터 상태와 대사 테스트."""

from __future__ import annotations

from datetime import datetime, timezone

from maidops_tui.characters.mio import DIALOGUES, FACES, dialogue_for, portrait
from maidops_tui.characters.state import derive_character_state
from maidops_tui.domain.models import (
    CharacterState,
    ConnectionStatus,
    DataOrigin,
    ErrorCase,
    ErrorLabel,
    Job,
    JobStatus,
    LabelSource,
    ReviewStatus,
)


def _job(status: JobStatus, suffix: str) -> Job:
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    return Job(
        id=f"job-{suffix}",
        project_id="demo-api",
        task_id="api-db-check",
        status=status,
        created_at=now,
        started_at=now,
        finished_at=now if status not in {JobStatus.RUNNING, JobStatus.QUEUED} else None,
        cancel_requested_at=None,
    )


def _case(status: ReviewStatus) -> ErrorCase:
    return ErrorCase(
        id="case-0001",
        job_id="job-0001",
        project_id="demo-api",
        raw_text="virtual error",
        draft_label=ErrorLabel.DB_CONNECTION,
        draft_source=LabelSource.FIXTURE,
        current_label=ErrorLabel.DB_CONNECTION,
        review_status=status,
        revisions=[],
        origin=DataOrigin.SESSION,
    )


def test_every_state_has_original_face_and_dialogue() -> None:
    faces = [FACES[state] for state in CharacterState]
    lines = [DIALOGUES[state] for state in CharacterState]
    assert len(set(faces)) == len(faces)
    assert len(set(lines)) == len(lines)
    for state in CharacterState:
        assert FACES[state] in portrait(state)
        assert dialogue_for(state) == DIALOGUES[state]
    assert "성공" not in DIALOGUES[CharacterState.FAILED]
    assert "학습" not in DIALOGUES[CharacterState.FAILED]
    assert "학습" not in DIALOGUES[CharacterState.NEEDS_REVIEW]


def test_running_job_is_working_even_with_a_draft() -> None:
    state = derive_character_state(
        connection=ConnectionStatus.DEMO,
        jobs=[_job(JobStatus.RUNNING, "0001")],
        error_cases=[_case(ReviewStatus.DRAFT)],
    )
    assert state is CharacterState.WORKING


def test_draft_needs_review_and_decided_failure_stays_failed() -> None:
    failed = _job(JobStatus.FAILED, "0001")
    assert (
        derive_character_state(
            connection=ConnectionStatus.DEMO,
            jobs=[failed],
            error_cases=[_case(ReviewStatus.DRAFT)],
        )
        is CharacterState.NEEDS_REVIEW
    )
    assert (
        derive_character_state(
            connection=ConnectionStatus.DEMO,
            jobs=[failed],
            error_cases=[_case(ReviewStatus.APPROVED)],
        )
        is CharacterState.FAILED
    )


def test_queued_job_is_not_described_as_running() -> None:
    state = derive_character_state(
        connection=ConnectionStatus.CONNECTED,
        jobs=[_job(JobStatus.QUEUED, "0004")],
        error_cases=[],
    )
    assert state is CharacterState.IDLE
    samples = [
        derive_character_state(connection=ConnectionStatus.DEMO, jobs=[], error_cases=[]),
        derive_character_state(
            connection=ConnectionStatus.DEMO,
            jobs=[_job(JobStatus.SUCCEEDED, "0002")],
            error_cases=[_case(ReviewStatus.REVISED)],
        ),
        derive_character_state(
            connection=ConnectionStatus.DISCONNECTED,
            jobs=[_job(JobStatus.RUNNING, "0003")],
            error_cases=[],
        ),
    ]
    assert CharacterState.TRAINING not in samples
    assert CharacterState.REPORTING not in samples
    assert samples[0] is CharacterState.IDLE
    assert samples[2] is CharacterState.DISCONNECTED


def test_training_and_reporting_follow_the_lab_not_a_label_approval() -> None:
    from maidops_tui.domain.models import ClassScore, LabStatus, ModelSummary

    failed = _job(JobStatus.FAILED, "0001")
    approved = _case(ReviewStatus.APPROVED)
    assert (
        derive_character_state(
            connection=ConnectionStatus.DEMO,
            jobs=[failed],
            error_cases=[approved],
        )
        is CharacterState.FAILED
    )
    running = _lab(active_run_status="RUNNING")
    assert (
        derive_character_state(
            connection=ConnectionStatus.CONNECTED,
            jobs=[],
            error_cases=[],
            lab=running,
        )
        is CharacterState.TRAINING
    )
    assert (
        derive_character_state(
            connection=ConnectionStatus.DISCONNECTED,
            jobs=[],
            error_cases=[],
            lab=running,
        )
        is CharacterState.DISCONNECTED
    )
    model = ModelSummary(
        id="mv-00000001",
        training_run_id="run-00000001",
        is_default=False,
        device="cpu",
        macro_f1=0.5,
        baseline_macro_f1=0.25,
        per_class=(ClassScore("OTHER", 0.5, 0.5, 0.5, 2),),
        confusion_matrix=((2,),),
        baseline_per_class=(ClassScore("OTHER", 0.25, 0.25, 0.25, 2),),
        baseline_confusion_matrix=((2,),),
        probability_note="softmax 출력은 보정된 정답 확률이 아닙니다.",
    )
    reporting = _lab(latest_model=model)
    assert reporting.awaiting_model_choice() is True
    assert (
        derive_character_state(
            connection=ConnectionStatus.CONNECTED,
            jobs=[failed],
            error_cases=[approved],
            lab=reporting,
        )
        is CharacterState.REPORTING
    )


def _lab(**overrides: object):
    from maidops_tui.domain.models import LabStatus

    values: dict[str, object] = {
        "eligible": False,
        "reasons": (),
        "confirmed_count": 0,
        "draft_count": 0,
        "deferred_count": 0,
        "class_counts": (),
        "train_count": 0,
        "val_count": 0,
        "test_count": 0,
        "active_run_id": None,
        "active_run_status": None,
        "default_model": None,
        "latest_model": None,
        "models": (),
        "embedding_id": "hashing-char-ngram-v1",
        "download_required": False,
    }
    values.update(overrides)
    return LabStatus(**values)  # type: ignore[arg-type]
