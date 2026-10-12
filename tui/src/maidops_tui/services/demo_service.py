"""메모리 위에서만 동작하는 가상 작업 서비스.

실제 셸, 파일, 네트워크, 모델에 접근하지 않는다.
작업 완료는 해당 작업의 토큰과 상태가 여전히 RUNNING일 때만 반영한다.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone

from maidops_tui.domain.display import format_connection
from maidops_tui.domain.errors import NotFoundError, StateError
from maidops_tui.domain.rules import classify_failure
from maidops_tui.domain.models import (
    CANCELLABLE_JOB_STATUSES,
    ConnectionStatus,
    DataOrigin,
    ErrorCase,
    ErrorLabel,
    Job,
    JobStatus,
    LabelRevision,
    LabelSource,
    LabStatus,
    OutputLine,
    Project,
    RegisteredTask,
    ResolutionRecord,
    ReviewDecision,
    ReviewStatus,
    RunPlan,
    SearchHit,
    SearchKind,
    ServiceEvent,
    VirtualOutcome,
)
from maidops_tui.services.fixtures import PROJECTS, SEED_RESOLUTIONS, TASKS

_LISTENER = Callable[[ServiceEvent], None]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DemoService:
    def __init__(self, *, delay_seconds: float = 1.0, log_limit: int = 200) -> None:
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be >= 0")
        if log_limit < 1:
            raise ValueError("log_limit must be >= 1")
        self.delay_seconds = delay_seconds
        self.log_limit = log_limit
        self._lock = asyncio.Lock()
        self._closed = False
        self._projects = {project.id: project for project in PROJECTS}
        self._tasks = dict(TASKS)
        self._selected_project_id = PROJECTS[0].id
        self._selected_task_id: str | None = None
        self._jobs: dict[str, Job] = {}
        self._outputs: dict[str, list[OutputLine]] = {}
        self._output_seq: dict[str, int] = {}
        self._tokens: dict[str, int] = {}
        self._tasks_running: dict[str, asyncio.Task[None]] = {}
        self._cases: dict[str, ErrorCase] = {}
        self._resolutions: list[ResolutionRecord] = list(SEED_RESOLUTIONS)
        self._job_seq = 0
        self._case_seq = 0
        self._resolution_seq = 0
        self._listeners: list[_LISTENER] = []

    def connection_status(self) -> ConnectionStatus:
        return ConnectionStatus.DEMO

    def connection_label(self) -> str:
        return format_connection(ConnectionStatus.DEMO)

    def worker_connected(self) -> bool:
        return False

    def add_listener(self, listener: _LISTENER) -> None:
        self._listeners.append(listener)

    async def aclose(self) -> None:
        self._closed = True
        pending = [task for task in self._tasks_running.values() if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def list_projects(self) -> list[Project]:
        return list(PROJECTS)

    async def select_project(self, project_id: str) -> Project:
        project = self._projects.get(project_id)
        if project is None:
            known = ", ".join(item.id for item in PROJECTS)
            raise NotFoundError(
                f"프로젝트를 찾지 못했습니다: {project_id}. 등록된 id: {known}",
                "/project select demo-api",
            )
        async with self._lock:
            self._selected_project_id = project.id
            self._selected_task_id = None
        self._emit(ServiceEvent("project_changed", project.id))
        return project

    async def get_selected_project(self) -> Project | None:
        if self._selected_project_id is None:
            return None
        return self._projects[self._selected_project_id]

    async def list_tasks(self) -> list[RegisteredTask]:
        project = await self.get_selected_project()
        if project is None:
            return []
        return [task for task in self._tasks.values() if task.project_id == project.id]

    async def select_task(self, task_id: str) -> RegisteredTask:
        tasks = await self.list_tasks()
        task = next((item for item in tasks if item.id == task_id), None)
        if task is None:
            raise NotFoundError(f"이 프로젝트의 등록 작업을 찾지 못했습니다: {task_id}", "/project list")
        self._selected_task_id = task.id
        self._emit(ServiceEvent("project_changed", task.id))
        return task

    async def get_run_plan(self) -> RunPlan:
        project = await self.get_selected_project()
        if project is None:
            raise StateError("선택된 프로젝트가 없습니다.", "/project select demo-api")
        return RunPlan(project=project, task=self._selected_task(project))

    def _selected_task(self, project: Project) -> RegisteredTask:
        task_id = self._selected_task_id or project.default_task_id
        task = self._require_task(task_id)
        if task.project_id != project.id:
            return self._require_task(project.default_task_id)
        return task

    async def create_test_job(self) -> Job:
        async with self._lock:
            if self._closed:
                raise StateError("서비스가 이미 종료되었습니다.")
            project = self._projects[self._selected_project_id]
            task = self._selected_task(project)
            self._job_seq += 1
            job_id = f"job-{self._job_seq:04d}"
            now = _utcnow()
            job = Job(
                id=job_id,
                project_id=project.id,
                task_id=task.id,
                status=JobStatus.RUNNING,
                created_at=now,
                started_at=now,
                finished_at=None,
                cancel_requested_at=None,
            )
            self._jobs[job_id] = job
            self._outputs[job_id] = []
            self._output_seq[job_id] = 0
            token = 1
            self._tokens[job_id] = token
            self._append_locked(
                job_id,
                "DEMO virtual event. This line is not a shell command.",
            )
            self._append_locked(job_id, f"fixture={task.id} project={project.id}")
            self._append_locked(job_id, "실제 셸, 프로젝트 파일, 네트워크, 모델에는 접근하지 않습니다.")
            runner = asyncio.create_task(self._finish_later(job_id, token))
            self._tasks_running[job_id] = runner
            snapshot = self._copy_job(job)
        self._emit(ServiceEvent("job_changed", job_id))
        return snapshot

    async def list_jobs(self) -> list[Job]:
        async with self._lock:
            jobs = [self._copy_job(job) for job in self._jobs.values()]
        jobs.sort(key=lambda job: (job.created_at, job.id))
        return jobs

    async def get_job(self, job_id: str) -> Job:
        async with self._lock:
            return self._copy_job(self._require_job(job_id))

    async def cancel_job(self, job_id: str) -> Job:
        async with self._lock:
            job = self._require_job(job_id)
            if job.status not in CANCELLABLE_JOB_STATUSES:
                raise StateError(
                    f"이미 종료된 작업은 취소할 수 없습니다: {job.id} {job.status.value}",
                    "/jobs",
                )
            self._tokens[job_id] = self._tokens.get(job_id, 0) + 1
            now = _utcnow()
            job.status = JobStatus.CANCEL_REQUESTED
            job.cancel_requested_at = now
            self._append_locked(job_id, "CANCEL requested")
            job.status = JobStatus.CANCELLED
            job.finished_at = now
            self._append_locked(job_id, "RESULT CANCELLED")
            snapshot = self._copy_job(job)
        self._emit(ServiceEvent("job_changed", job_id))
        return snapshot

    async def get_job_output(self, job_id: str) -> list[OutputLine]:
        async with self._lock:
            self._require_job(job_id)
            return list(self._outputs[job_id])

    async def list_error_cases(self) -> list[ErrorCase]:
        async with self._lock:
            cases = [self._copy_case(case) for case in self._cases.values()]
        cases.sort(key=lambda case: case.id)
        return cases

    async def get_error_case(self, case_id: str) -> ErrorCase:
        async with self._lock:
            return self._copy_case(self._require_case(case_id))

    async def review_error_case(
        self,
        case_id: str,
        decision: ReviewDecision,
        label: ErrorLabel | None = None,
    ) -> ErrorCase:
        async with self._lock:
            case = self._require_case(case_id)
            note = self._apply_review_locked(case, decision, label)
            case.revisions.append(
                LabelRevision(
                    at=_utcnow(),
                    label=case.current_label,
                    review_status=case.review_status,
                    source=LabelSource.USER,
                    note=note,
                )
            )
            snapshot = self._copy_case(case)
        self._emit(ServiceEvent("review_changed", case_id))
        return snapshot

    async def save_resolution(self, case_id: str, cause: str, method: str) -> ResolutionRecord:
        cause_text = cause.strip()
        method_text = method.strip()
        if not cause_text or not method_text:
            raise StateError("원인과 해결 방법을 모두 입력하세요.", "원인과 방법을 입력한 뒤 저장")
        if len(cause_text) > 500 or len(method_text) > 500:
            raise StateError("원인과 해결 방법은 각각 500자 이하여야 합니다.")
        async with self._lock:
            case = self._require_case(case_id)
            if case.review_status not in {ReviewStatus.APPROVED, ReviewStatus.REVISED}:
                raise StateError(
                    "승인 또는 수정된 사례만 해결 기록으로 저장할 수 있습니다. 보류와 초안은 제외됩니다.",
                    "라벨을 승인하거나 수정한 뒤 저장하세요.",
                )
            self._resolution_seq += 1
            record = ResolutionRecord(
                id=f"resolution-{self._resolution_seq:04d}",
                error_case_id=case.id,
                project_id=case.project_id,
                label=case.current_label,
                cause=cause_text,
                method=method_text,
                origin=DataOrigin.SESSION,
                created_at=_utcnow(),
            )
            self._resolutions.append(record)
        self._emit(ServiceEvent("resolution_changed", record.id))
        return record

    async def list_resolutions(self) -> list[ResolutionRecord]:
        async with self._lock:
            return list(self._resolutions)

    async def search_history(self, query: str) -> list[SearchHit]:
        keyword = query.strip()
        if not keyword:
            raise StateError("검색어가 비어 있습니다.", "postgres")
        folded = keyword.casefold()
        async with self._lock:
            hits: list[SearchHit] = []
            for job in self._jobs.values():
                blob = " ".join(
                    [
                        job.id,
                        job.project_id,
                        job.task_id,
                        job.status.value,
                        *(line.text for line in self._outputs.get(job.id, [])),
                    ]
                )
                if folded in blob.casefold():
                    hits.append(
                        SearchHit(
                            kind=SearchKind.JOB,
                            origin=DataOrigin.SESSION,
                            title=f"{job.id} {job.status.value}",
                            excerpt=f"project={job.project_id} task={job.task_id}",
                        )
                    )
            for case in self._cases.values():
                blob = " ".join(
                    [
                        case.id,
                        case.job_id,
                        case.current_label.value,
                        case.draft_label.value,
                        case.review_status.value,
                        case.raw_text,
                    ]
                )
                if folded in blob.casefold():
                    hits.append(
                        SearchHit(
                            kind=SearchKind.ERROR_CASE,
                            origin=case.origin,
                            title=(
                                f"{case.id} {case.draft_source.value} {case.review_status.value} "
                                f"{case.draft_label.value}"
                            ),
                            excerpt=_excerpt(case.raw_text),
                        )
                    )
            for record in self._resolutions:
                blob = " ".join(
                    [
                        record.id,
                        record.error_case_id,
                        record.project_id,
                        record.label.value,
                        record.cause,
                        record.method,
                    ]
                )
                if folded in blob.casefold():
                    hits.append(
                        SearchHit(
                            kind=SearchKind.RESOLUTION,
                            origin=record.origin,
                            title=f"{record.id} {record.label.value}",
                            excerpt=_excerpt(f"{record.cause} {record.method}"),
                        )
                    )
        return hits

    async def lab_status(self) -> LabStatus:
        async with self._lock:
            cases = list(self._cases.values())
        confirmed = [case for case in cases if case.confirmed_label is not None]
        counts = {label.value: 0 for label in ErrorLabel}
        for case in confirmed:
            assert case.confirmed_label is not None
            counts[case.confirmed_label.value] += 1
        return LabStatus(
            eligible=False,
            reasons=(
                "DEMO에서는 학습하지 않습니다. 확정 라벨은 이 세션 메모리에만 있으며 종료하면 사라집니다.",
            ),
            confirmed_count=len(confirmed),
            draft_count=sum(case.review_status is ReviewStatus.DRAFT for case in cases),
            deferred_count=sum(case.review_status is ReviewStatus.DEFERRED for case in cases),
            class_counts=tuple(counts.items()),
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

    async def start_training(self) -> str:
        raise StateError(
            "DEMO에서는 학습하지 않습니다. 평가 점수를 만들지 않습니다.",
            "LIVE에서 확정 라벨이 학습 조건을 만족한 뒤 시작하세요.",
        )

    async def cancel_training(self, run_id: str) -> str:
        del run_id
        raise StateError("DEMO에는 취소할 학습이 없습니다.", "/lab")

    async def select_default_model(self, model_id: str) -> str:
        del model_id
        raise StateError("DEMO에는 선택할 모델이 없습니다. 점수를 만들지 않습니다.", "/lab")

    async def _finish_later(self, job_id: str, token: int) -> None:
        try:
            await asyncio.sleep(self.delay_seconds)
        except asyncio.CancelledError:
            return
        await self._apply_virtual_completion(job_id, token)

    async def _apply_virtual_completion(self, job_id: str, token: int) -> None:
        changed = False
        async with self._lock:
            if self._closed:
                return
            if self._tokens.get(job_id) != token:
                return
            job = self._jobs.get(job_id)
            if job is None or job.status is not JobStatus.RUNNING:
                return
            task = self._require_task(job.task_id)
            for line in task.output_lines:
                self._append_locked(job_id, line)
            if task.outcome is VirtualOutcome.PASS:
                job.status = JobStatus.SUCCEEDED
                self._append_locked(job_id, "RESULT PASS")
            else:
                job.status = JobStatus.FAILED
                self._append_locked(job_id, "RESULT FAIL")
                self._create_case_locked(job)
            job.finished_at = _utcnow()
            changed = True
        if changed:
            self._emit(ServiceEvent("job_changed", job_id))

    def _apply_review_locked(
        self,
        case: ErrorCase,
        decision: ReviewDecision,
        label: ErrorLabel | None,
    ) -> str:
        if decision is ReviewDecision.APPROVE:
            case.review_status = ReviewStatus.APPROVED
            return "사용자가 초안 라벨을 승인했습니다. 학습은 시작하지 않습니다."
        if decision is ReviewDecision.DEFER:
            case.review_status = ReviewStatus.DEFERRED
            return "사용자가 검토를 보류했습니다. 학습 정답에서 제외됩니다."
        if decision is ReviewDecision.REVISE:
            if label is None or label is case.current_label:
                raise StateError(
                    "수정하려면 현재와 다른 라벨을 선택하세요.",
                    "OTHER",
                )
            case.current_label = label
            case.review_status = ReviewStatus.REVISED
            return "사용자가 라벨을 수정했습니다. 학습은 시작하지 않습니다."
        raise StateError(f"지원하지 않는 검토 결정입니다: {decision.value}")

    def _create_case_locked(self, job: Job) -> None:
        self._case_seq += 1
        case_id = f"case-{self._case_seq:04d}"
        raw_text = "\n".join(line.text for line in self._outputs[job.id])
        draft = classify_failure(raw_text)
        keyword = draft.matched_keyword or "없음"
        now = _utcnow()
        case = ErrorCase(
            id=case_id,
            job_id=job.id,
            project_id=job.project_id,
            raw_text=raw_text,
            draft_label=draft.label,
            draft_source=LabelSource.RULE_BASED,
            current_label=draft.label,
            review_status=ReviewStatus.DRAFT,
            revisions=[
                LabelRevision(
                    at=now,
                    label=draft.label,
                    review_status=ReviewStatus.DRAFT,
                    source=LabelSource.RULE_BASED,
                    note=(
                        f"규칙 기반 초안입니다. 규칙 버전 {draft.rule_version}. "
                        f"일치 키워드: {keyword}. 이 값은 정답 확률이 아닙니다."
                    ),
                )
            ],
            origin=DataOrigin.SESSION,
            rule_version=draft.rule_version,
            matched_keyword=draft.matched_keyword,
        )
        self._cases[case_id] = case

    def _append_locked(self, job_id: str, text: str) -> None:
        sequence = self._output_seq[job_id] + 1
        self._output_seq[job_id] = sequence
        self._outputs[job_id].append(OutputLine(sequence=sequence, text=text))
        self._trim_locked(job_id)

    def _trim_locked(self, job_id: str) -> None:
        lines = self._outputs[job_id]
        if len(lines) <= self.log_limit:
            return
        self._jobs[job_id].output_truncated = True
        if self.log_limit == 1:
            self._outputs[job_id] = [lines[-1]]
            return
        tail = lines[-(self.log_limit - 1) :]
        marker_sequence = self._output_seq[job_id] + 1
        self._output_seq[job_id] = marker_sequence
        marker = OutputLine(
            sequence=marker_sequence,
            text=f"[출력 잘림] 최근 {self.log_limit}줄만 표시합니다.",
        )
        self._outputs[job_id] = [marker, *tail]

    def _require_job(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise NotFoundError(f"작업을 찾지 못했습니다: {job_id}", "/jobs")
        return job

    def _require_case(self, case_id: str) -> ErrorCase:
        case = self._cases.get(case_id)
        if case is None:
            raise NotFoundError(f"오류 사례를 찾지 못했습니다: {case_id}", "/review")
        return case

    def _require_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task is None:
            raise NotFoundError(f"등록된 가상 작업을 찾지 못했습니다: {task_id}")
        return task

    def _copy_job(self, job: Job) -> Job:
        return replace(job)

    def _copy_case(self, case: ErrorCase) -> ErrorCase:
        return replace(case, revisions=list(case.revisions))

    def _emit(self, event: ServiceEvent) -> None:
        for listener in tuple(self._listeners):
            listener(event)


def _excerpt(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"
