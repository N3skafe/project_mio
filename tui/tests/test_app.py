"""Textual 앱 상호작용 테스트."""

from __future__ import annotations

from textual.widgets import Button, ContentSwitcher, Static

from maidops_tui.domain.models import JobStatus, LabelSource, ReviewStatus, RunMode, ScreenId
from maidops_tui.screens.help_screen import HelpScreen
from tests.support import make_app, rich_log_text, submit, wait_for, wait_for_terminal_jobs


async def test_screen_keys_and_bad_command_keep_the_app_alive() -> None:
    app = make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        assert app.query_one("#views", ContentSwitcher).current == "workspace"
        await pilot.press("f3")
        assert app.query_one("#views", ContentSwitcher).current == ScreenId.REVIEW.value
        await pilot.press("f4")
        assert app.query_one("#views", ContentSwitcher).current == ScreenId.LAB.value
        await pilot.press("f5")
        assert app.query_one("#views", ContentSwitcher).current == ScreenId.HISTORY.value
        await pilot.press("f2")
        assert app.query_one("#views", ContentSwitcher).current == ScreenId.WORKSPACE.value
        await submit(pilot, app, "/nope")
        assert app.is_running
        assert any("지원하지 않는 명령" in line for line in app.activity_lines)
        assert app.query_one("#views", ContentSwitcher).current == ScreenId.WORKSPACE.value


async def test_priority_keys_work_while_command_input_is_focused() -> None:
    app = make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        app.query_one("#command-input").focus()
        await pilot.press("f3")
        assert app.query_one("#views", ContentSwitcher).current == "review"
        await pilot.press("ctrl+l")
        assert app.focused is not None
        assert app.focused.id == "command-input"


async def test_help_and_quiet_mode() -> None:
    app = make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        await pilot.press("f1")
        await pilot.pause(0.6)
        assert isinstance(app.screen, HelpScreen)
        assert "/cancel" in str(app.screen.query_one("#help-text", Static).content)
        await pilot.press("escape")
        await pilot.pause()
        await submit(pilot, app, "/quiet on")
        assert app.query_one("#character-line", Static).display is False
        assert app.query_one("#character-status", Static).display is True
        assert "대사 숨김" in str(app.query_one("#quiet-flag", Static).content)
        assert "DEMO · 가상 이벤트" in str(app.query_one("#character-mode", Static).content)
        await submit(pilot, app, "/quiet off")
        assert app.query_one("#character-line", Static).display is True


async def test_demo_failure_review_and_lab_stays_disabled() -> None:
    app = make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        assert "DEMO(가상, 백엔드 없음)" in str(app.query_one("#top-bar", Static).content)
        await submit(pilot, app, "/test")
        jobs = await wait_for_terminal_jobs(pilot, app)
        assert jobs[-1].status is JobStatus.FAILED

        def failed_log() -> bool:
            return "RESULT FAIL" in rich_log_text(app.query_one("#job-log"))

        await wait_for(pilot, failed_log)
        await wait_for(
            pilot,
            lambda: "NEEDS_REVIEW" in str(app.query_one("#character-status", Static).content),
        )
        await pilot.press("f3")
        await pilot.pause()
        detail = str(app.query_one("#error-text", Static).content)
        info = str(app.query_one("#label-info", Static).content)
        assert "RULE_BASED" in info
        assert "확정 라벨: 없음" in info
        assert "정답 확률" in info
        pending = await app.service.list_error_cases()
        assert pending[0].draft_source is LabelSource.RULE_BASED
        assert pending[0].confirmed_label is None
        assert "virtual" in detail.casefold() or "ERROR" in detail
        app.query_one("#approve-button", Button).press()
        await pilot.pause()
        cases = await app.service.list_error_cases()
        assert cases[0].review_status is ReviewStatus.APPROVED
        assert any("학습은 시작하지 않습니다" in line for line in app.activity_lines)
        assert "TRAINING" not in str(app.query_one("#character-status", Static).content)
        await pilot.press("f4")
        await pilot.pause()
        notice = str(app.query_one("#lab-notice", Static).content)
        summary = str(app.query_one("#lab-summary", Static).content)
        assert "DEMO에서는 학습하지 않습니다" in notice
        assert app.query_one("#train-button", Button).disabled is True
        assert app.query_one("#compare-button", Button).disabled is True
        assert app.query_one("#select-model-button", Button).disabled is True
        assert "평가 점수는 표시하지 않습니다" in summary
        assert "F1" not in summary
        assert "확정(승인+수정): 1" in summary


async def test_cancel_from_command_is_not_reported_as_pass() -> None:
    app = make_app(demo_delay_seconds=2.0)
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        await submit(pilot, app, "/test")
        jobs = await app.service.list_jobs()
        assert jobs[0].status is JobStatus.RUNNING
        await submit(pilot, app, f"/cancel {jobs[0].id}")
        current = await app.service.get_job(jobs[0].id)
        texts = [line.text for line in await app.service.get_job_output(jobs[0].id)]
        assert current.status is JobStatus.CANCELLED
        assert "RESULT CANCELLED" in texts
        assert "RESULT PASS" not in texts
        assert "RESULT FAIL" not in texts
        assert any("취소했습니다" in line for line in app.activity_lines)


async def test_history_keyword_search_marks_fixture_data() -> None:
    app = make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        await submit(pilot, app, "/history")
        box = app.query_one("#history-query")
        box.value = "5432"
        await box.action_submit()
        await pilot.pause()

        def found() -> bool:
            text = rich_log_text(app.query_one("#history-results"))
            return "5432" in text and "FIXTURE" in text

        await wait_for(pilot, found)


async def test_character_update_does_not_clear_log_or_steal_focus() -> None:
    app = make_app()
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        await submit(pilot, app, "/test")
        await wait_for_terminal_jobs(pilot, app)
        await wait_for(pilot, lambda: "RESULT FAIL" in rich_log_text(app.query_one("#job-log")))
        before_lines = len(app.query_one("#job-log").lines)
        before_activity = list(app.activity_lines)
        app.query_one("#command-input").focus()
        await submit(pilot, app, "/quiet on")
        assert app.focused is not None
        assert app.focused.id == "command-input"
        assert len(app.query_one("#job-log").lines) >= before_lines
        assert before_activity[0] in app.activity_lines
        assert "RESULT FAIL" in rich_log_text(app.query_one("#job-log"))


async def test_fresh_app_does_not_reuse_previous_session() -> None:
    first = make_app()
    async with first.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, first, "/test")
        await wait_for_terminal_jobs(pilot, first)
        assert await first.service.list_error_cases()
    second = make_app()
    async with second.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert await second.service.list_jobs() == []
        assert await second.service.list_error_cases() == []


async def test_narrow_layout_still_accepts_commands() -> None:
    app = make_app()
    async with app.run_test(size=(78, 24)) as pilot:
        await pilot.pause()
        assert app.query_one("#character-status", Static).display is True
        await submit(pilot, app, "/help")
        assert any("도움말" in line for line in app.activity_lines)
        await pilot.press("f4")
        assert app.query_one("#train-button", Button).disabled is True


async def test_live_mode_screen_shows_disconnected() -> None:
    from maidops_tui.app import MaidOpsApp
    from maidops_tui.config import AppConfig
    from tests.test_demo_service import _disconnected_service

    app = MaidOpsApp(
        config=AppConfig(
            mode=RunMode.LIVE,
            backend_url="http://127.0.0.1:9",
            demo_delay_seconds=0.05,
        ),
        service=_disconnected_service(),
    )
    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause()
        await wait_for(
            pilot,
            lambda: "DISCONNECTED" in str(app.query_one("#character-status", Static).content),
        )
        assert "DISCONNECTED" in str(app.query_one("#top-bar", Static).content)
        await submit(pilot, app, "/test")
        assert any("백엔드에 연결하지 못했습니다" in line for line in app.activity_lines)
        assert any("성공으로 처리하지 않습니다" in line for line in app.activity_lines)
        assert app.service.connection_status().value == "DISCONNECTED"
