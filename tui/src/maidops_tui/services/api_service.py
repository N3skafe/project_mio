"""LIVE 모드에서 Spring Boot API를 호출한다.

실행 워커가 없으므로 서버가 QUEUED로 저장한 작업을 성공으로 바꾸지 않는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

import httpx

from maidops_tui.domain.errors import LiveModeUnavailable, NotFoundError, StateError
from maidops_tui.domain.models import (
    ClassScore,
    ConnectionStatus,
    DataOrigin,
    ErrorCase,
    ErrorLabel,
    Job,
    JobStatus,
    LabelRevision,
    LabelSource,
    LabStatus,
    ModelSummary,
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
)

_LISTENER = Callable[[ServiceEvent], None]


class ApiService:
    def __init__(self, base_url: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(5.0, connect=2.0),
        )
        self._status = ConnectionStatus.DISCONNECTED
        self._worker_state = "NOT_CONNECTED"
        self._selected_project_id: str | None = None
        self._selected_task_id: str | None = None
        self._listeners: list[_LISTENER] = []

    def connection_status(self) -> ConnectionStatus:
        return self._status

    def connection_label(self) -> str:
        if self._status is not ConnectionStatus.CONNECTED:
            return "DISCONNECTED"
        if self._worker_state == "CONNECTED":
            return "CONNECTED"
        return "CONNECTED(실행 워커 없음)"

    def worker_connected(self) -> bool:
        return self._worker_state == "CONNECTED"

    def add_listener(self, listener: _LISTENER) -> None:
        self._listeners.append(listener)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def list_projects(self) -> list[Project]:
        payload = await self._get_json("/api/v1/projects")
        projects = [_project(item) for item in payload["items"]]
        if self._selected_project_id is None and projects:
            preferred = next((item for item in projects if item.id == "demo-api"), projects[0])
            self._selected_project_id = preferred.id
        return projects

    async def select_project(self, project_id: str) -> Project:
        payload = await self._get_json(f"/api/v1/projects/{project_id}")
        project = _project(payload)
        self._selected_project_id = project.id
        self._selected_task_id = None
        self._emit(ServiceEvent("project_changed", project.id))
        return project

    async def get_selected_project(self) -> Project | None:
        if self._selected_project_id is None:
            await self.list_projects()
        if self._selected_project_id is None:
            return None
        payload = await self._get_json(f"/api/v1/projects/{self._selected_project_id}")
        return _project(payload)

    async def list_tasks(self) -> list[RegisteredTask]:
        project = await self.get_selected_project()
        if project is None:
            return []
        payload = await self._get_json(f"/api/v1/projects/{project.id}/tasks")
        return [_task(item) for item in payload["items"]]

    async def select_task(self, task_id: str) -> RegisteredTask:
        task = next((item for item in await self.list_tasks() if item.id == task_id), None)
        if task is None:
            raise NotFoundError(f"이 프로젝트의 등록 작업을 찾지 못했습니다: {task_id}", "/project list")
        self._selected_task_id = task.id
        self._emit(ServiceEvent("project_changed", task.id))
        return task

    async def get_run_plan(self) -> RunPlan:
        project = await self.get_selected_project()
        if project is None:
            raise StateError("선택된 프로젝트가 없습니다.", "/project select demo-api")
        tasks = await self.list_tasks()
        chosen = self._selected_task_id
        task = next((item for item in tasks if item.id == chosen), None)
        if task is None:
            task = next((item for item in tasks if item.id == project.default_task_id), None)
        if task is None:
            raise StateError("프로젝트의 기본 작업이 없습니다.", "/project list")
        return RunPlan(project=project, task=task)

    async def create_test_job(self) -> Job:
        plan = await self.get_run_plan()
        payload = await self._send_json(
            "POST",
            "/api/v1/jobs",
            json={"project_id": plan.project.id, "task_id": plan.task.id},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        job = _job(payload)
        if job.status is not JobStatus.QUEUED:
            raise StateError(
                f"서버가 대기 상태가 아닌 작업을 반환했습니다: {job.status.value}. 이 클라이언트는 그 결과를 성공으로 해석하지 않습니다.",
                "/jobs",
            )
        self._emit(ServiceEvent("job_changed", job.id))
        return job

    async def list_jobs(self) -> list[Job]:
        rows = await self._collect("/api/v1/jobs")
        jobs = [_job(item) for item in rows]
        jobs.sort(key=lambda job: (job.created_at, job.id))
        return jobs

    async def get_job(self, job_id: str) -> Job:
        return _job(await self._get_json(f"/api/v1/jobs/{job_id}"))

    async def cancel_job(self, job_id: str) -> Job:
        job = _job(await self._send_json("POST", f"/api/v1/jobs/{job_id}/cancel"))
        self._emit(ServiceEvent("job_changed", job.id))
        return job

    async def get_job_output(self, job_id: str) -> list[OutputLine]:
        payload = await self._get_json(f"/api/v1/jobs/{job_id}/events")
        return [
            OutputLine(sequence=int(item["sequence"]), text=str(item["text"]))
            for item in payload["items"]
        ]

    async def list_error_cases(self) -> list[ErrorCase]:
        rows = await self._collect("/api/v1/error-cases")
        cases = [_case(item) for item in rows]
        cases.sort(key=lambda case: case.id)
        return cases

    async def get_error_case(self, case_id: str) -> ErrorCase:
        return _case(await self._get_json(f"/api/v1/error-cases/{case_id}"))

    async def review_error_case(
        self,
        case_id: str,
        decision: ReviewDecision,
        label: ErrorLabel | None = None,
    ) -> ErrorCase:
        body: dict[str, str] = {"decision": decision.value}
        if label is not None:
            body["label"] = label.value
        case = _case(await self._send_json("POST", f"/api/v1/error-cases/{case_id}/reviews", json=body))
        self._emit(ServiceEvent("review_changed", case.id))
        return case

    async def save_resolution(self, case_id: str, cause: str, method: str) -> ResolutionRecord:
        payload = await self._send_json(
            "POST",
            f"/api/v1/error-cases/{case_id}/resolutions",
            json={"cause": cause, "method": method},
        )
        record = _resolution(payload)
        self._emit(ServiceEvent("resolution_changed", record.id))
        return record

    async def list_resolutions(self) -> list[ResolutionRecord]:
        payload = await self._get_json("/api/v1/resolutions")
        return [_resolution(item) for item in payload["items"]]

    async def search_history(self, query: str) -> list[SearchHit]:
        keyword = query.strip()
        if not keyword:
            raise StateError("검색어가 비어 있습니다.", "postgres")
        payload = await self._get_json("/api/v1/search", params={"q": keyword})
        return [_hit(item) for item in payload["items"]]

    async def lab_status(self) -> LabStatus:
        payload = await self._get_json("/api/v1/lab/status")
        models = tuple(_model(item) for item in payload.get("models") or [])
        active = payload.get("active_run") or {}
        return LabStatus(
            eligible=bool(payload.get("eligible")),
            reasons=tuple(str(item) for item in payload.get("reasons") or []),
            confirmed_count=int(payload.get("confirmed_count") or 0),
            draft_count=int(payload.get("draft_count") or 0),
            deferred_count=int(payload.get("deferred_count") or 0),
            class_counts=tuple(
                (str(item["label"]), int(item["count"])) for item in payload.get("class_counts") or []
            ),
            train_count=int((payload.get("split_preview") or {}).get("train") or 0),
            val_count=int((payload.get("split_preview") or {}).get("val") or 0),
            test_count=int((payload.get("split_preview") or {}).get("test") or 0),
            active_run_id=None if not active else str(active.get("id") or "") or None,
            active_run_status=None if not active else str(active.get("status") or "") or None,
            default_model=_optional_model(payload.get("default_model")),
            latest_model=_optional_model(payload.get("latest_model")),
            models=models,
            embedding_id=str(payload.get("embedding_id") or ""),
            download_required=bool(payload.get("download_required")),
        )

    async def start_training(self) -> str:
        payload = await self._send_json("POST", "/api/v1/training-runs")
        run_id = str(payload.get("id") or "")
        self._emit(ServiceEvent("training_changed", run_id))
        return run_id

    async def cancel_training(self, run_id: str) -> str:
        payload = await self._send_json("POST", f"/api/v1/training-runs/{run_id}/cancel")
        self._emit(ServiceEvent("training_changed", run_id))
        return str(payload.get("status") or "")

    async def select_default_model(self, model_id: str) -> str:
        payload = await self._send_json("POST", f"/api/v1/model-versions/{model_id}/select-default")
        self._emit(ServiceEvent("model_changed", model_id))
        if payload.get("is_default") is not True:
            raise StateError("서버가 기본 모델로 표시하지 않았습니다.", "/lab")
        return model_id

    async def _collect(self, path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(10):
            params: dict[str, str | int] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            payload = await self._get_json(path, params=params)
            items.extend(payload["items"])
            cursor = payload.get("next_cursor")
            if not cursor:
                return items
        raise StateError("목록이 표시 한도를 넘었습니다.", path)

    async def _get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self._send_json("GET", path, params=params)

    async def _send_json(self, method: str, path: str, **kwargs: Any) -> Any:
        await self._ensure_healthy()
        response = await self._send(method, path, **kwargs)
        if response.status_code >= 400:
            self._raise_api(response)
        if response.status_code != 204 and response.content:
            return response.json()
        return {}

    async def _ensure_healthy(self) -> None:
        response = await self._send("GET", "/api/v1/health")
        if response.status_code != 200:
            self._status = ConnectionStatus.DISCONNECTED
            raise LiveModeUnavailable(
                f"백엔드 상태 확인에 실패했습니다. {self._base_url} 데이터베이스 연결을 확인하세요. 작업을 저장하지 않았습니다.",
                "Docker Compose의 postgres와 backend healthcheck를 확인하세요.",
            )
        body = response.json()
        if body.get("status") != "UP" or body.get("database") != "UP":
            self._status = ConnectionStatus.DISCONNECTED
            self._worker_state = "NOT_CONNECTED"
            raise LiveModeUnavailable(
                "백엔드가 데이터베이스에 연결되지 않았습니다. 작업을 저장하지 않았습니다.",
                "Docker Compose의 postgres healthcheck를 확인하세요.",
            )
        self._worker_state = str(body.get("worker") or "NOT_CONNECTED")
        self._status = ConnectionStatus.CONNECTED

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            self._status = ConnectionStatus.DISCONNECTED
            raise LiveModeUnavailable(
                f"백엔드에 연결하지 못했습니다. {self._base_url} 에 연결할 수 없습니다. 작업을 저장하지 않았고 성공으로 처리하지 않습니다.",
                "infra의 Docker Compose를 실행한 뒤 MAIDOPS_MODE=LIVE 로 다시 여세요.",
            ) from exc
        except httpx.TimeoutException as exc:
            self._status = ConnectionStatus.DISCONNECTED
            raise LiveModeUnavailable(
                f"백엔드 응답이 시간 초과되었습니다. {self._base_url} 작업을 저장하지 않았고 성공으로 처리하지 않습니다.",
                "서버 health를 확인하세요.",
            ) from exc

    def _raise_api(self, response: httpx.Response) -> None:
        message = f"백엔드가 HTTP {response.status_code}을 반환했습니다."
        example = ""
        code = ""
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            message = str(body.get("message") or message)
            example = str(body.get("example") or "")
            code = str(body.get("code") or "")
        self._status = ConnectionStatus.CONNECTED
        if response.status_code == 404 or code == "NOT_FOUND":
            raise NotFoundError(message, example)
        if response.status_code >= 500:
            self._status = ConnectionStatus.DISCONNECTED
            raise LiveModeUnavailable(message, example or "백엔드 로그를 확인하세요.")
        raise StateError(message, example)

    def _emit(self, event: ServiceEvent) -> None:
        for listener in tuple(self._listeners):
            listener(event)


def _project(item: dict[str, Any]) -> Project:
    return Project(
        id=str(item["id"]),
        name=str(item["name"]),
        summary=str(item["summary"]),
        default_task_id=str(item["default_task_id"]),
    )


def _task(item: dict[str, Any]) -> RegisteredTask:
    return RegisteredTask(
        id=str(item["id"]),
        project_id=str(item["project_id"]),
        name=str(item["name"]),
        plan_text=str(item["plan_text"]),
        outcome=None,
        draft_label=None,
        output_lines=(),
    )


def _job(item: dict[str, Any]) -> Job:
    created_at = _instant(item["created_at"])
    if created_at is None:
        raise StateError("서버 응답에 created_at이 없습니다.", "/jobs")
    return Job(
        id=str(item["id"]),
        project_id=str(item["project_id"]),
        task_id=str(item["task_id"]),
        status=JobStatus(str(item["status"])),
        created_at=created_at,
        started_at=_instant(item.get("started_at")),
        finished_at=_instant(item.get("finished_at")),
        cancel_requested_at=_instant(item.get("cancel_requested_at")),
        output_truncated=bool(item.get("output_truncated", False)),
    )


def _case(item: dict[str, Any]) -> ErrorCase:
    revisions = [
        LabelRevision(
            at=_instant(revision["created_at"]),
            label=ErrorLabel(str(revision["label"])),
            review_status=ReviewStatus(str(revision["review_status"])),
            source=LabelSource(str(revision["source"])),
            note=str(revision["note"]),
        )
        for revision in item.get("revisions", [])
    ]
    return ErrorCase(
        id=str(item["id"]),
        job_id=str(item["job_id"]),
        project_id=str(item["project_id"]),
        raw_text=str(item["raw_text"]),
        draft_label=None if item.get("draft_label") is None else ErrorLabel(str(item["draft_label"])),
        draft_source=LabelSource(str(item["draft_source"])),
        current_label=None if item.get("current_label") is None else ErrorLabel(str(item["current_label"])),
        review_status=ReviewStatus(str(item["review_status"])),
        revisions=revisions,
        origin=DataOrigin(str(item["origin"])),
        rule_version=None if item.get("rule_version") is None else str(item["rule_version"]),
        matched_keyword=None if item.get("matched_keyword") is None else str(item["matched_keyword"]),
        inference_state=str(item.get("inference_state") or "READY"),
        model_version_id=None if item.get("model_version_id") is None else str(item["model_version_id"]),
    )


def _resolution(item: dict[str, Any]) -> ResolutionRecord:
    return ResolutionRecord(
        id=str(item["id"]),
        error_case_id=str(item["error_case_id"]),
        project_id=str(item["project_id"]),
        label=ErrorLabel(str(item["label"])),
        cause=str(item["cause"]),
        method=str(item["method"]),
        origin=DataOrigin(str(item["origin"])),
        created_at=_instant(item["created_at"]),
    )


def _hit(item: dict[str, Any]) -> SearchHit:
    return SearchHit(
        kind=SearchKind(str(item["kind"])),
        origin=DataOrigin(str(item["origin"])),
        title=str(item["title"]),
        excerpt=str(item["excerpt"]),
    )


def _optional_model(value: Any) -> ModelSummary | None:
    if not isinstance(value, dict):
        return None
    return _model(value)


def _model(item: dict[str, Any]) -> ModelSummary:
    return ModelSummary(
        id=str(item["id"]),
        training_run_id=str(item["training_run_id"]),
        is_default=bool(item.get("is_default")),
        device=str(item.get("device") or ""),
        macro_f1=float(item["macro_f1"]),
        baseline_macro_f1=float(item["baseline_macro_f1"]),
        per_class=_scores(item.get("per_class") or []),
        confusion_matrix=_matrix(item.get("confusion_matrix") or []),
        baseline_per_class=_scores(item.get("baseline_per_class") or []),
        baseline_confusion_matrix=_matrix(item.get("baseline_confusion_matrix") or []),
        probability_note=str(item.get("probability_note") or ""),
    )


def _scores(items: list[dict[str, Any]]) -> tuple[ClassScore, ...]:
    return tuple(
        ClassScore(
            label=str(item["label"]),
            precision=None if item.get("precision") is None else float(item["precision"]),
            recall=None if item.get("recall") is None else float(item["recall"]),
            f1=None if item.get("f1") is None else float(item["f1"]),
            support=int(item.get("support") or 0),
        )
        for item in items
    )


def _matrix(rows: list[list[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(value) for value in row) for row in rows)


def _instant(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
