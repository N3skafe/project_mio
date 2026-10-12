"""가상 서비스의 작업, 취소, 검토, 검색 테스트."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from maidops_tui.domain.display import summarize_cases
from maidops_tui.domain.errors import LiveModeUnavailable, NotFoundError, StateError
from maidops_tui.domain.models import (
    DataOrigin,
    ErrorLabel,
    JobStatus,
    LabelSource,
    ReviewDecision,
    ReviewStatus,
    SearchKind,
)
from maidops_tui.services.api_service import ApiService
from maidops_tui.services.demo_service import DemoService


async def test_fail_and_pass_jobs_do_not_overwrite_each_other() -> None:
    service = DemoService(delay_seconds=0.05, log_limit=50)
    try:
        await service.select_project("demo-api")
        failed = await service.create_test_job()
        await service.select_project("demo-web")
        passed = await service.create_test_job()
        await asyncio.sleep(0.2)
        failed_now = await service.get_job(failed.id)
        passed_now = await service.get_job(passed.id)
        assert failed_now.status is JobStatus.FAILED
        assert passed_now.status is JobStatus.SUCCEEDED
        assert failed_now.project_id == "demo-api"
        assert passed_now.project_id == "demo-web"
        failed_text = [line.text for line in await service.get_job_output(failed.id)]
        passed_text = [line.text for line in await service.get_job_output(passed.id)]
        assert "RESULT FAIL" in failed_text
        assert "RESULT PASS" not in failed_text
        assert "RESULT PASS" in passed_text
        assert "RESULT FAIL" not in passed_text
    finally:
        await service.aclose()


async def test_cancel_blocks_late_success_event() -> None:
    service = DemoService(delay_seconds=0.25, log_limit=50)
    try:
        await service.select_project("demo-web")
        job = await service.create_test_job()
        cancelled = await service.cancel_job(job.id)
        assert cancelled.status is JobStatus.CANCELLED
        assert cancelled.cancel_requested_at is not None
        await service._apply_virtual_completion(job.id, token=1)
        await service._apply_virtual_completion(job.id, token=2)
        await asyncio.sleep(0.45)
        current = await service.get_job(job.id)
        texts = [line.text for line in await service.get_job_output(job.id)]
        assert current.status is JobStatus.CANCELLED
        assert "CANCEL requested" in texts
        assert "RESULT CANCELLED" in texts
        assert "RESULT PASS" not in texts
        assert "RESULT FAIL" not in texts
    finally:
        await service.aclose()


async def test_review_approve_revise_defer_and_resolution() -> None:
    service = DemoService(delay_seconds=0.05, log_limit=50)
    try:
        job = await service.create_test_job()
        await asyncio.sleep(0.2)
        cases = await service.list_error_cases()
        assert len(cases) == 1
        case = cases[0]
        assert case.job_id == job.id
        assert case.draft_source is LabelSource.RULE_BASED
        assert case.rule_version == "rules-1"
        assert case.matched_keyword == ":5432"
        assert case.review_status is ReviewStatus.DRAFT
        assert case.draft_label is ErrorLabel.DB_CONNECTION
        assert case.confirmed_label is None
        with pytest.raises(StateError):
            await service.save_resolution(case.id, "원인", "방법")
        with pytest.raises(StateError):
            await service.review_error_case(case.id, ReviewDecision.REVISE, ErrorLabel.DB_CONNECTION)
        revised = await service.review_error_case(case.id, ReviewDecision.REVISE, ErrorLabel.AUTH_PERMISSION)
        assert revised.review_status is ReviewStatus.REVISED
        assert revised.current_label is ErrorLabel.AUTH_PERMISSION
        assert revised.revisions[-1].source is LabelSource.USER
        assert revised.confirmed_label is ErrorLabel.AUTH_PERMISSION
        assert revised.draft_label is ErrorLabel.DB_CONNECTION
        deferred = await service.review_error_case(case.id, ReviewDecision.DEFER)
        assert deferred.review_status is ReviewStatus.DEFERRED
        assert deferred.confirmed_label is None
        assert summarize_cases(await service.list_error_cases()).confirmed == 0
        approved = await service.review_error_case(case.id, ReviewDecision.APPROVE)
        assert approved.review_status is ReviewStatus.APPROVED
        assert approved.confirmed_label is ErrorLabel.AUTH_PERMISSION
        assert approved.draft_label is ErrorLabel.DB_CONNECTION
        assert summarize_cases(await service.list_error_cases()).confirmed == 1
        record = await service.save_resolution(case.id, "가상 소켓이 거절됨", "포트를 확인")
        assert record.origin is DataOrigin.SESSION
        hits = await service.search_history("포트")
        assert any(hit.kind is SearchKind.RESOLUTION and hit.origin is DataOrigin.SESSION for hit in hits)
    finally:
        await service.aclose()


async def test_new_service_does_not_keep_previous_reviews() -> None:
    first = DemoService(delay_seconds=0.05, log_limit=20)
    try:
        await first.create_test_job()
        await asyncio.sleep(0.2)
        case = (await first.list_error_cases())[0]
        await first.review_error_case(case.id, ReviewDecision.APPROVE)
    finally:
        await first.aclose()
    second = DemoService(delay_seconds=0.05, log_limit=20)
    try:
        assert await second.list_jobs() == []
        assert await second.list_error_cases() == []
        assert all(record.origin is DataOrigin.FIXTURE for record in await second.list_resolutions())
    finally:
        await second.aclose()


async def test_keyword_search_distinguishes_fixture_records() -> None:
    service = DemoService(delay_seconds=1.0, log_limit=20)
    try:
        hits = await service.search_history("5432")
        assert hits
        assert all(hit.origin is DataOrigin.FIXTURE for hit in hits)
        assert await service.search_history("없는키워드zzz") == []
        with pytest.raises(StateError):
            await service.search_history("   ")
    finally:
        await service.aclose()


async def test_output_is_trimmed_with_a_visible_marker() -> None:
    service = DemoService(delay_seconds=0.05, log_limit=3)
    try:
        job = await service.create_test_job()
        await asyncio.sleep(0.2)
        output = await service.get_job_output(job.id)
        current = await service.get_job(job.id)
        assert current.output_truncated is True
        assert len(output) <= 3
        assert output[0].text.startswith("[출력 잘림]")
        assert any(line.text == "RESULT FAIL" for line in output)
    finally:
        await service.aclose()


async def test_unknown_project_and_terminal_cancel() -> None:
    service = DemoService(delay_seconds=0.05, log_limit=20)
    try:
        with pytest.raises(NotFoundError):
            await service.select_project("missing")
        job = await service.create_test_job()
        await asyncio.sleep(0.2)
        with pytest.raises(StateError):
            await service.cancel_job(job.id)
    finally:
        await service.aclose()


async def test_selected_task_replaces_the_project_default() -> None:
    service = DemoService(delay_seconds=0)
    try:
        await service.select_project("demo-web")
        await service.select_task("web-health")
        selected = await service.create_test_job()
        assert selected.task_id == "web-health"
        await service.select_project("demo-api")
        restored = await service.create_test_job()
        assert restored.task_id == "api-db-check"
    finally:
        await service.aclose()


async def test_live_mode_refuses_without_pretending_success() -> None:
    service = _disconnected_service()
    try:
        assert service.connection_status().value == "DISCONNECTED"
        with pytest.raises(LiveModeUnavailable) as caught:
            await service.create_test_job()
        assert "백엔드에 연결하지 못했습니다" in caught.value.message
        assert "성공으로 처리하지 않습니다" in caught.value.message
    finally:
        await service.aclose()


def _disconnected_service() -> ApiService:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(refuse), base_url="http://127.0.0.1:9")
    return ApiService("http://127.0.0.1:9", client=client)
