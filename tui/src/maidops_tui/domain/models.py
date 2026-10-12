"""PHASE 1 세션에서 쓰는 도메인 모델.

PHASE 2의 영속 엔티티와 이름을 맞추되, 이 단계의 데이터는 프로세스 메모리에만 있다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RunMode(StrEnum):
    DEMO = "DEMO"
    LIVE = "LIVE"


class ConnectionStatus(StrEnum):
    """백엔드 연결 상태.

    DEMO는 네트워크가 연결된 상태가 아니다.
    가상 세션이며 백엔드 프로세스가 없다는 뜻이다.
    """

    DEMO = "DEMO"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"


class ScreenId(StrEnum):
    WORKSPACE = "workspace"
    REVIEW = "review"
    LAB = "lab"
    HISTORY = "history"


class CharacterState(StrEnum):
    IDLE = "IDLE"
    WORKING = "WORKING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"
    TRAINING = "TRAINING"
    REPORTING = "REPORTING"
    DISCONNECTED = "DISCONNECTED"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


ACTIVE_JOB_STATUSES = frozenset(
    {
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.CANCEL_REQUESTED,
    }
)
TERMINAL_JOB_STATUSES = frozenset(
    {
        JobStatus.SUCCEEDED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    }
)
CANCELLABLE_JOB_STATUSES = frozenset(
    {
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.CANCEL_REQUESTED,
    }
)


class ErrorLabel(StrEnum):
    DB_CONNECTION = "DB_CONNECTION"
    AUTH_PERMISSION = "AUTH_PERMISSION"
    EXTERNAL_NETWORK = "EXTERNAL_NETWORK"
    INPUT_VALIDATION = "INPUT_VALIDATION"
    OTHER = "OTHER"


class LabelSource(StrEnum):
    """라벨이 어디서 왔는지.

    실패 로그의 예측 초안은 RULE_BASED다. FIXTURE는 가상 해결 기록에 남는다.
    MODEL은 기본 모델이 만든 실패 로그 초안이다. 미검토 초안은 확정 라벨이 아니다.
    """

    FIXTURE = "FIXTURE"
    RULE_BASED = "RULE_BASED"
    MODEL = "MODEL"
    USER = "USER"
    LOG = "LOG"


class ReviewStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REVISED = "REVISED"
    DEFERRED = "DEFERRED"


class ReviewDecision(StrEnum):
    APPROVE = "APPROVE"
    REVISE = "REVISE"
    DEFER = "DEFER"


class DataOrigin(StrEnum):
    FIXTURE = "FIXTURE"
    SESSION = "SESSION"


class VirtualOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    summary: str
    default_task_id: str


@dataclass(frozen=True)
class RegisteredTask:
    """등록된 가상 작업.

    셸 문자열이 아니다. PHASE 1에서는 이 계획을 프로세스로 실행하지 않는다.
    """

    id: str
    project_id: str
    name: str
    plan_text: str
    outcome: VirtualOutcome | None = None
    draft_label: ErrorLabel | None = None
    output_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunPlan:
    project: Project
    task: RegisteredTask

    def describe(self) -> str:
        lines = [
            f"프로젝트: {self.project.name} ({self.project.id})",
            f"작업: {self.task.name} ({self.task.id})",
            f"계획: {self.task.plan_text}",
        ]
        if self.task.outcome is None:
            lines.append("예정된 성공이나 실패는 없습니다. 실행 워커가 없으면 작업은 QUEUED로 남습니다.")
        else:
            lines.append(
                f"예정된 가상 결과: {self.task.outcome.value} "
                "(실행 전 시나리오이며, 이번 실행의 실제 결과가 아닙니다.)"
            )
            lines.append("실제 셸, 프로젝트 파일, 네트워크, 모델에는 접근하지 않습니다.")
        return "\n".join(lines)


@dataclass(frozen=True)
class OutputLine:
    sequence: int
    text: str


@dataclass
class Job:
    id: str
    project_id: str
    task_id: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    cancel_requested_at: datetime | None
    output_truncated: bool = False

    def elapsed_seconds(self, now: datetime) -> float:
        start = self.started_at or self.created_at
        end = self.finished_at or now
        return max(0.0, (end - start).total_seconds())


@dataclass(frozen=True)
class LabelRevision:
    at: datetime
    label: ErrorLabel
    review_status: ReviewStatus
    source: LabelSource
    note: str


@dataclass
class ErrorCase:
    id: str
    job_id: str
    project_id: str
    raw_text: str
    draft_label: ErrorLabel | None
    draft_source: LabelSource
    current_label: ErrorLabel | None
    review_status: ReviewStatus
    revisions: list[LabelRevision]
    origin: DataOrigin
    rule_version: str | None = None
    matched_keyword: str | None = None
    inference_state: str = "READY"
    model_version_id: str | None = None

    @property
    def confirmed_label(self) -> ErrorLabel | None:
        """승인 또는 수정된 라벨만 확정이다. 초안과 보류는 빠진다."""

        if self.review_status in {ReviewStatus.APPROVED, ReviewStatus.REVISED}:
            return self.current_label
        return None


@dataclass(frozen=True)
class ResolutionRecord:
    id: str
    error_case_id: str
    project_id: str
    label: ErrorLabel
    cause: str
    method: str
    origin: DataOrigin
    created_at: datetime


class SearchKind(StrEnum):
    JOB = "JOB"
    ERROR_CASE = "ERROR_CASE"
    RESOLUTION = "RESOLUTION"


@dataclass(frozen=True)
class SearchHit:
    kind: SearchKind
    origin: DataOrigin
    title: str
    excerpt: str


@dataclass(frozen=True)
class ServiceEvent:
    kind: str
    subject_id: str


@dataclass(frozen=True)
class ClassScore:
    label: str
    precision: float | None
    recall: float | None
    f1: float | None
    support: int


@dataclass(frozen=True)
class ModelSummary:
    id: str
    training_run_id: str
    is_default: bool
    device: str
    macro_f1: float
    baseline_macro_f1: float
    per_class: tuple[ClassScore, ...]
    confusion_matrix: tuple[tuple[int, ...], ...]
    baseline_per_class: tuple[ClassScore, ...]
    baseline_confusion_matrix: tuple[tuple[int, ...], ...]
    probability_note: str


@dataclass(frozen=True)
class LabStatus:
    eligible: bool
    reasons: tuple[str, ...]
    confirmed_count: int
    draft_count: int
    deferred_count: int
    class_counts: tuple[tuple[str, int], ...]
    train_count: int
    val_count: int
    test_count: int
    active_run_id: str | None
    active_run_status: str | None
    default_model: ModelSummary | None
    latest_model: ModelSummary | None
    models: tuple[ModelSummary, ...]
    embedding_id: str
    download_required: bool

    def awaiting_model_choice(self) -> bool:
        if self.latest_model is None:
            return False
        if self.default_model is None:
            return True
        return self.default_model.id != self.latest_model.id


@dataclass(frozen=True)
class ReviewCounts:
    draft: int
    approved: int
    revised: int
    deferred: int

    @property
    def confirmed(self) -> int:
        return self.approved + self.revised
