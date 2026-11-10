"""LIVE 등록·가져오기 호출과 DEMO 거절."""

from __future__ import annotations

import json

import httpx
import pytest

from maidops_tui.domain.errors import StateError
from maidops_tui.domain.models import DataOrigin, LabelSource
from maidops_tui.services.api_service import ApiService
from maidops_tui.services.demo_service import DemoService


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/v1/health":
        return httpx.Response(
            200,
            json={"status": "UP", "database": "UP", "worker": "NOT_CONNECTED", "authentication": "NONE"},
        )
    if request.url.path == "/api/v1/projects" and request.method == "POST":
        body = json.loads(request.content.decode())
        return httpx.Response(
            201,
            json={
                "id": body["id"],
                "name": body["name"],
                "summary": body["summary"],
                "default_task_id": None,
            },
        )
    if request.url.path == "/api/v1/projects/my-api/tasks" and request.method == "POST":
        body = json.loads(request.content.decode())
        assert body["argv_json"] == ["{python}", "pass_check.py"]
        return httpx.Response(
            201,
            json={
                "id": body["id"],
                "project_id": "my-api",
                "name": body["name"],
                "plan_text": body["plan_text"],
                "argv_json": json.dumps(body["argv_json"]),
                "relative_workdir": body["relative_workdir"],
                "timeout_seconds": body["timeout_seconds"],
            },
        )
    if request.url.path == "/api/v1/projects/my-api":
        return httpx.Response(
            200,
            json={"id": "my-api", "name": "내 API", "summary": "설명", "default_task_id": "my-check"},
        )
    if request.url.path == "/api/v1/error-cases/import" and request.method == "POST":
        body = json.loads(request.content.decode())
        assert body["raw_log"] == "Connection to localhost:5432 refused"
        return httpx.Response(
            201,
            json={
                "id": "case-import",
                "job_id": None,
                "project_id": body["project_id"],
                "raw_text": body["raw_log"],
                "draft_label": "DB_CONNECTION",
                "draft_source": "RULE_BASED",
                "current_label": "DB_CONNECTION",
                "review_status": "DRAFT",
                "origin": "IMPORT",
                "rule_version": "rules-1",
                "matched_keyword": "postgresql",
                "confirmed_label": None,
                "inference_state": "READY",
                "model_version_id": None,
                "source_hint": body.get("source_hint"),
                "created_at": "2026-11-10T00:00:00Z",
                "revisions": [],
            },
        )
    return httpx.Response(404, json={"code": "NOT_FOUND", "message": "없음", "example": ""})


async def test_api_service_posts_registration_and_import() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler), base_url="http://backend.test")
    service = ApiService("http://backend.test", client=client)
    try:
        project = await service.register_project("my-api", "내 API", "설명")
        assert project.id == "my-api"
        assert project.default_task_id is None
        task = await service.register_task(
            "my-api",
            "my-check",
            "통과 점검",
            "등록된 스크립트만 실행합니다.",
            "sample",
            "pass_check.py",
            10,
        )
        assert task.id == "my-check"
        case = await service.import_failure_log("trusted-sample", "Connection to localhost:5432 refused", "지난 배포")
        assert case.origin is DataOrigin.IMPORT
        assert case.job_id is None
        assert case.draft_source is LabelSource.RULE_BASED
        assert case.source_hint == "지난 배포"
        assert case.confirmed_label is None
    finally:
        await service.aclose()


async def test_demo_refuses_registration_and_import() -> None:
    service = DemoService(delay_seconds=0.01, log_limit=20)
    try:
        with pytest.raises(StateError, match="LIVE에서만"):
            await service.register_project("my-api", "내 API", "")
        with pytest.raises(StateError, match="LIVE에서만"):
            await service.register_task("demo-api", "my-check", "이름", "계획", "sample", "pass_check.py", 10)
        with pytest.raises(StateError, match="LIVE에서만"):
            await service.import_failure_log("demo-api", "boom")
    finally:
        await service.aclose()
