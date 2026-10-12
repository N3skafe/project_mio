"""ApiService가 서버의 QUEUED 응답을 그대로 두고, 연결 실패를 성공으로 바꾸지 않는지 확인한다."""

from __future__ import annotations

import json

import httpx

from maidops_tui.domain.models import JobStatus
from maidops_tui.services.api_service import ApiService


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/v1/health":
        return httpx.Response(
            200,
            json={
                "status": "UP",
                "database": "UP",
                "worker": "NOT_CONNECTED",
                "authentication": "NONE",
            },
        )
    if request.url.path == "/api/v1/projects" and request.method == "GET":
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "demo-api",
                        "name": "데모 API",
                        "summary": "등록 프로젝트",
                        "default_task_id": "api-db-check",
                    }
                ],
                "next_cursor": None,
            },
        )
    if request.url.path == "/api/v1/projects/demo-api/tasks":
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "api-db-check",
                        "project_id": "demo-api",
                        "name": "DB 연결 점검 자리",
                        "plan_text": "워커가 없으면 QUEUED로 남습니다.",
                    }
                ]
            },
        )
    if request.url.path == "/api/v1/projects/demo-api":
        return httpx.Response(
            200,
            json={
                "id": "demo-api",
                "name": "데모 API",
                "summary": "등록 프로젝트",
                "default_task_id": "api-db-check",
            },
        )
    if request.url.path == "/api/v1/jobs" and request.method == "POST":
        body = json.loads(request.content.decode())
        assert request.headers["Idempotency-Key"]
        return httpx.Response(
            201,
            json={
                "id": "job-00000042",
                "project_id": body["project_id"],
                "task_id": body["task_id"],
                "status": "QUEUED",
                "created_at": "2026-10-06T10:00:00Z",
                "started_at": None,
                "finished_at": None,
                "cancel_requested_at": None,
                "output_truncated": False,
            },
        )
    if request.url.path == "/api/v1/jobs/job-00000042/events":
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "sequence": 1,
                        "text": "QUEUED. 실행 워커가 연결되지 않아 이 작업은 대기 상태로 남습니다.",
                        "created_at": "2026-10-06T10:00:00Z",
                    }
                ],
                "next_cursor": None,
            },
        )
    return httpx.Response(404, json={"code": "NOT_FOUND", "message": "없음", "example": ""})


async def test_api_service_keeps_queued_job() -> None:
    transport = httpx.MockTransport(_handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://backend.test")
    service = ApiService("http://backend.test", client=client)
    try:
        job = await service.create_test_job()
        assert job.status is JobStatus.QUEUED
        assert job.started_at is None
        output = await service.get_job_output(job.id)
        assert all("RESULT PASS" not in line.text and "RESULT FAIL" not in line.text for line in output)
        assert service.connection_label() == "CONNECTED(실행 워커 없음)"
        plan = await service.get_run_plan()
        assert plan.task.outcome is None
        assert "QUEUED" in plan.describe()
    finally:
        await service.aclose()
