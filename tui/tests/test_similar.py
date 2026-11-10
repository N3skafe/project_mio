"""확정 기록만 해시 코사인으로 찾고, 없으면 없다고 말한다."""

from __future__ import annotations

import asyncio

from maidops_tui.domain.models import ReviewDecision, SearchKind
from maidops_tui.domain.similarity import EMPTY_ANSWER, embed
from maidops_tui.services.demo_service import DemoService


def test_hash_fingerprint_matches_the_trainer_buckets() -> None:
    vector = embed("Connection to localhost:5432 refused")
    assert abs(vector[1] + 0.09245) < 1e-4
    assert abs(vector[8] - 0.1849) < 1e-4


async def test_demo_similar_search_cites_confirmed_resolution_only() -> None:
    service = DemoService(delay_seconds=0.05, log_limit=50)
    try:
        await service.create_test_job()
        await asyncio.sleep(0.2)
        case = (await service.list_error_cases())[0]
        before = await service.similar_search(raw_log=case.raw_text)
        assert before.answer == EMPTY_ANSWER
        assert all(hit.hit_id != case.id for hit in before.hits)
        await service.review_error_case(case.id, ReviewDecision.APPROVE)
        record = await service.save_resolution(case.id, "phase7-cause-socket", "phase7-method-port")
        advice = await service.similar_search(raw_log=case.raw_text)
        assert advice.hits
        assert advice.hits[0].kind is SearchKind.RESOLUTION
        assert advice.hits[0].hit_id == record.id
        assert "phase7-cause-socket" in advice.answer
        assert "phase7-method-port" in advice.answer
        assert record.id in advice.answer
        own = await service.similar_search(error_case_id=case.id)
        assert all(hit.error_case_id != case.id for hit in own.hits)
        assert record.id not in own.answer
        unrelated = await service.similar_search(raw_log="disk quota exceeded while writing the artifact")
        assert unrelated.answer == EMPTY_ANSWER
        assert unrelated.hits == ()
        keyword = await service.search_history("phase7-cause-socket")
        assert any(hit.kind is SearchKind.RESOLUTION for hit in keyword)
    finally:
        await service.aclose()
