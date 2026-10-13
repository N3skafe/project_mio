"""화면과 명령 출력이 함께 쓰는 표시 문구."""

from __future__ import annotations

from datetime import datetime

from maidops_tui.domain.models import (
    ConnectionStatus,
    DataOrigin,
    ErrorCase,
    ErrorLabel,
    Job,
    JobStatus,
    LabStatus,
    ModelSummary,
    ReviewCounts,
    ReviewStatus,
    RunMode,
)
_STATUS_WORDS = {
    JobStatus.QUEUED: "QUEUED",
    JobStatus.RUNNING: "RUNNING",
    JobStatus.SUCCEEDED: "PASS",
    JobStatus.FAILED: "FAIL",
    JobStatus.CANCEL_REQUESTED: "CANCEL_REQUESTED",
    JobStatus.CANCELLED: "CANCELLED",
}


def display_status(status: JobStatus) -> str:
    """성공·실패는 색에만 기대지 않도록 PASS / FAIL 문자로 보여 준다."""

    return _STATUS_WORDS[status]


def format_elapsed(seconds: float) -> str:
    return f"{seconds:.1f}s"


def format_connection(status: ConnectionStatus) -> str:
    if status is ConnectionStatus.DEMO:
        return "DEMO(가상, 백엔드 없음)"
    if status is ConnectionStatus.DISCONNECTED:
        return "DISCONNECTED"
    return "CONNECTED"


def format_header(
    *,
    project_name: str,
    mode: RunMode,
    connection_label: str,
) -> str:
    return (
        f"MaidOps Lab  프로젝트: {project_name}  "
        f"모드: {mode.value}  연결: {connection_label}"
    )


def format_job_meta(job: Job, now: datetime) -> str:
    notes: list[str] = []
    if job.termination_reason in {"OUTPUT_LIMIT_EXCEEDED", "SUPERVISION_FAILED", "TIMED_OUT"}:
        notes.append(job.termination_reason)
    if job.output_truncated and job.termination_reason != "OUTPUT_LIMIT_EXCEEDED":
        notes.append("출력 잘림")
    if job.log_storage_incomplete:
        notes.append("로그 일부 미저장")
    suffix = "".join(f"  {note}" for note in notes)
    return (
        f"{job.id}  {display_status(job.status)}  "
        f"경과 {format_elapsed(job.elapsed_seconds(now))}  "
        f"task {job.task_id}{suffix}"
    )


def summarize_cases(cases: list[ErrorCase]) -> ReviewCounts:
    session = [case for case in cases if case.origin is DataOrigin.SESSION]
    return ReviewCounts(
        draft=sum(case.review_status is ReviewStatus.DRAFT for case in session),
        approved=sum(case.review_status is ReviewStatus.APPROVED for case in session),
        revised=sum(case.review_status is ReviewStatus.REVISED for case in session),
        deferred=sum(case.review_status is ReviewStatus.DEFERRED for case in session),
    )


def format_lab_summary(counts: ReviewCounts) -> str:
    return format_lab_status(
        LabStatus(
            eligible=False,
            reasons=("DEMO에서는 학습하지 않습니다. 확정 라벨은 이 세션 메모리에만 있으며 종료하면 사라집니다.",),
            confirmed_count=counts.confirmed,
            draft_count=counts.draft,
            deferred_count=counts.deferred,
            class_counts=tuple((label.value, 0) for label in ErrorLabel),
            train_count=0,
            val_count=0,
            test_count=0,
            active_run_id=None,
            active_run_status=None,
            default_model=None,
            latest_model=None,
            models=(),
            embedding_id="hashing-char-ngram-v1",
            download_required=False,
        )
    )


def empty_lab_status() -> LabStatus:
    return LabStatus(
        eligible=False,
        reasons=("연구실 상태를 가져오지 못했습니다.",),
        confirmed_count=0,
        draft_count=0,
        deferred_count=0,
        class_counts=tuple((label.value, 0) for label in ErrorLabel),
        train_count=0,
        val_count=0,
        test_count=0,
        active_run_id=None,
        active_run_status=None,
        default_model=None,
        latest_model=None,
        models=(),
        embedding_id="hashing-char-ngram-v1",
        download_required=False,
    )


def format_lab_status(status: LabStatus) -> str:
    lines = [
        "검토·확정 데이터",
        f"확정(승인+수정): {status.confirmed_count}",
        f"초안 DRAFT: {status.draft_count}",
        f"보류 DEFERRED: {status.deferred_count}",
        "클래스 분포 (확정만):",
    ]
    for label, count in status.class_counts:
        lines.append(f"  {label}: {count}")
    lines.append("보류와 미검토 초안은 학습 정답에서 제외됩니다.")
    lines.append(f"임베딩: {status.embedding_id}")
    lines.append("외부 모델 다운로드: 없음" if not status.download_required else "외부 모델 다운로드가 필요합니다.")
    lines.append(f"분할 미리보기 train/val/test: {status.train_count}/{status.val_count}/{status.test_count}")
    if status.reasons:
        lines.append("학습 조건:")
        lines.extend(f"- {reason}" for reason in status.reasons)
    else:
        lines.append("학습 조건을 만족합니다. 학습이 끝나도 기본 모델은 바뀌지 않습니다.")
    if status.active_run_id:
        lines.append(f"학습 작업: {status.active_run_id} {status.active_run_status}")
    if status.default_model is None:
        lines.append("기본 모델: 없음")
    else:
        lines.append(f"기본 모델: {status.default_model.id}")
    if status.latest_model is None:
        lines.append("평가 결과: 없음")
        lines.append("평가 점수는 표시하지 않습니다.")
    else:
        lines.append(format_model_comparison(status.latest_model))
    return "\n".join(lines)


def lab_notice(status: LabStatus) -> str:
    if status.active_run_status == "RUNNING":
        return "학습이 진행 중입니다. 점수는 끝난 뒤에만 표시합니다."
    if status.active_run_status == "QUEUED":
        return "학습이 대기 중입니다. 학습기가 가져가면 진행으로 바뀝니다."
    if status.reasons:
        return status.reasons[0]
    return "학습을 시작할 수 있습니다. 끝나도 기본 모델은 자동으로 바뀌지 않습니다."


def format_model_comparison(model: ModelSummary) -> str:
    verified = model.metric_policy == "supported-class-macro-f1-v2" and model.checkpoint_evaluated
    if verified:
        score_line = f"실제 표본이 있는 클래스 기준 macro F1: {_metric(model.macro_f1)}"
        policy_line = "평가 정책 supported-class-macro-f1-v2. 저장 파일을 다시 로드한 뒤의 테스트 분할 점수입니다."
    else:
        score_line = f"기록된 macro F1: {_metric(model.macro_f1)}"
        policy_line = "정책 미확인 legacy 기록입니다. 현재 macro F1과 같은 의미로 비교하지 않습니다."
    lines = [
        f"모델 {model.id}  장치 {model.device}  기본={'예' if model.is_default else '아니오'}",
        score_line,
        policy_line,
        f"규칙 baseline macro F1: {_metric(model.baseline_macro_f1)}",
        model.probability_note,
        "클래스별 모델 / 규칙 baseline:",
    ]
    if verified and model.included_labels:
        lines.insert(-1, "macro에 포함한 클래스: " + ", ".join(model.included_labels))
    baseline = {score.label: score for score in model.baseline_per_class}
    for score in model.per_class:
        other = baseline.get(score.label)
        lines.append(
            f"  {score.label}  모델 f1={_metric(score.f1)} support={score.support}"
            + (f"  baseline f1={_metric(other.f1)}" if other is not None else "")
        )
    lines.append("혼동행렬 행=정답 열=예측")
    lines.append("라벨 순서: " + ", ".join(score.label for score in model.per_class))
    lines.extend("  " + " ".join(str(value) for value in row) for row in model.confusion_matrix)
    lines.append("규칙 baseline 혼동행렬:")
    lines.extend("  " + " ".join(str(value) for value in row) for row in model.baseline_confusion_matrix)
    return "\n".join(lines)


def _metric(value: float | None) -> str:
    if value is None:
        return "없음"
    return f"{value:.4f}"
