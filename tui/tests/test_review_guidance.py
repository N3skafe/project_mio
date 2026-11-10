"""Review는 초안 근거, 유사 요약, 점검 목록을 보여주고 점수를 만들지 않는다."""

from __future__ import annotations

from textual.widgets import Static

from maidops_tui.domain.models import (
    DataOrigin,
    ErrorCase,
    ErrorLabel,
    LabelSource,
    ReviewStatus,
)
from maidops_tui.domain.similarity import EMPTY_ANSWER
from maidops_tui.screens.review import _label_lines
from tests.support import make_app, submit, wait_for, wait_for_terminal_jobs


def test_pending_model_draft_says_review_waits() -> None:
    case = ErrorCase(
        id="case-pending",
        job_id="job-1",
        project_id="demo-api",
        raw_text="waiting",
        draft_label=None,
        draft_source=LabelSource.MODEL,
        current_label=None,
        review_status=ReviewStatus.DRAFT,
        revisions=[],
        origin=DataOrigin.SESSION,
        inference_state="PENDING",
        model_version_id="mv-00000007",
    )
    text = "\n".join(_label_lines(case))
    assert "MODEL" in text
    assert "mv-00000007" in text
    assert "초안 대기" in text
    assert "F1" not in text
    assert "정답 확률" in text


async def test_review_shows_rule_evidence_checklist_and_similar_summary() -> None:
    app = make_app()
    async with app.run_test(size=(120, 42)) as pilot:
        await pilot.pause()
        await submit(pilot, app, "/test")
        await wait_for_terminal_jobs(pilot, app)
        await pilot.press("f3")
        await pilot.pause()

        def ready() -> bool:
            info = str(app.query_one("#label-info", Static).content)
            checklist = str(app.query_one("#review-checklist", Static).content)
            advice = str(app.query_one("#similar-advice", Static).content)
            return (
                "RULE_BASED" in info
                and "rules-1" in info
                and "일치 키워드" in info
                and "DB_CONNECTION" in checklist
                and "호스트와 포트" in checklist
                and EMPTY_ANSWER in advice
                and "F1" not in checklist
                and "F1" not in advice
            )

        await wait_for(pilot, ready)
