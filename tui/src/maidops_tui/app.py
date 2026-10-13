"""MaidOps Lab Textual 앱.

캐릭터 패널은 상태를 설명할 뿐, 작업 로그와 입력 포커스를 건드리지 않는다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from textual.app import App, ComposeResult, ScreenStackError
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import ContentSwitcher, Footer, Input, RichLog, Static

from maidops_tui.characters.state import derive_character_state
from maidops_tui.commands.executor import run_command_text
from maidops_tui.config import AppConfig, load_config
from maidops_tui.domain.display import empty_lab_status, format_header
from maidops_tui.domain.errors import LabError
from maidops_tui.domain.models import (
    ACTIVE_JOB_STATUSES,
    CharacterState,
    ConnectionStatus,
    Project,
    RunMode,
    ScreenId,
    SearchHit,
    ServiceEvent,
)
from maidops_tui.screens.help_screen import HelpScreen
from maidops_tui.screens.history import HistoryView
from maidops_tui.screens.lab import LabView
from maidops_tui.screens.review import ReviewView
from maidops_tui.screens.workspace import WorkspaceView
from maidops_tui.services.factory import build_service
from maidops_tui.services.protocol import LabService
from maidops_tui.widgets.character_panel import CharacterPanel

_SCREEN_TITLES = {
    ScreenId.WORKSPACE: "Workspace",
    ScreenId.REVIEW: "Review",
    ScreenId.LAB: "Lab",
    ScreenId.HISTORY: "History",
}


class MaidOpsApp(App[None]):
    """터미널에서 동작하는 MaidOps Lab PHASE 1."""

    CSS_PATH = "styles/app.tcss"
    TITLE = "MaidOps Lab"
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (100, "-wide")]
    BINDINGS = [
        Binding("f1", "help", "도움말", priority=True),
        Binding("f2", "show_workspace", "Workspace", priority=True),
        Binding("f3", "show_review", "Review", priority=True),
        Binding("f4", "show_lab", "Lab", priority=True),
        Binding("f5", "show_history", "History", priority=True),
        Binding("ctrl+l", "focus_command", "명령", priority=True),
        Binding("ctrl+q", "quit", "종료", priority=True),
    ]

    def __init__(
        self,
        config: AppConfig | None = None,
        service: LabService | None = None,
    ) -> None:
        super().__init__()
        self.config = config if config is not None else load_config()
        self.service = service if service is not None else build_service(self.config)
        self.activity_lines: list[str] = []
        self.command_count = 0
        self.quiet = self.config.quiet
        self.pending_review_job_id: str | None = None
        self._character_state = CharacterState.IDLE
        self._closing = False
        self._refresh_running = False
        self._refresh_again = False
        self._refresh_lock = asyncio.Lock()
        self._clock = None
        self._poll_ticks = 0

    def compose(self) -> ComposeResult:
        yield Static(
            format_header(
                project_name="없음",
                mode=self.config.mode,
                connection_label=self.service.connection_label(),
            ),
            id="top-bar",
            markup=False,
        )
        with Container(id="body"):
            yield CharacterPanel()
            with Vertical(id="main"):
                yield ContentSwitcher(
                    WorkspaceView(),
                    ReviewView(),
                    LabView(),
                    HistoryView(),
                    id="views",
                    initial="workspace",
                )
        yield RichLog(
            id="activity-log",
            max_lines=200,
            wrap=True,
            markup=False,
            highlight=False,
            auto_scroll=True,
        )
        with Horizontal(id="command-row"):
            yield Static("명령", id="command-label", markup=False)
            yield Input(placeholder="/help", id="command-input")
        yield Footer()

    def on_mount(self) -> None:
        self.service.add_listener(self._on_service_event)
        self._query("#character", CharacterPanel).border_title = self.config.character_name
        self._query("#main", Vertical).border_title = "Workspace"
        self._render_character()
        if self.config.mode is RunMode.DEMO:
            self.write_activity(
                "DEMO 모드입니다. 가상 이벤트이며 실제 명령, 파일, 네트워크, 모델에 접근하지 않습니다."
            )
            self.write_activity("세션 데이터는 프로그램을 종료하면 사라집니다. 기본 프로젝트는 demo-api 입니다.")
        else:
            self.write_activity("LIVE 모드입니다. 백엔드에 작업을 저장합니다.")
        self._clock = self.set_interval(0.5, self._tick)
        self._enqueue_refresh()
        self._query("#command-input", Input).focus()

    async def on_unmount(self) -> None:
        self._closing = True
        if self._clock is not None:
            self._clock.stop()
        await self.service.aclose()

    def _ui_alive(self) -> bool:
        return not self._closing and bool(self.screen_stack)

    def _query(self, selector: str | type, expect_type: type | None = None):
        stack = self.screen_stack
        if not stack:
            raise NoMatches("화면이 이미 닫혔습니다.")
        shell = stack[0]
        if expect_type is None:
            return shell.query_one(selector)
        return shell.query_one(selector, expect_type)

    def action_help(self) -> None:
        if isinstance(self.screen, HelpScreen):
            return
        self.push_screen(HelpScreen())

    def action_show_workspace(self) -> None:
        self.show_screen(ScreenId.WORKSPACE)

    def action_show_review(self) -> None:
        self.show_screen(ScreenId.REVIEW)

    def action_show_lab(self) -> None:
        self.show_screen(ScreenId.LAB)

    def action_show_history(self) -> None:
        self.show_screen(ScreenId.HISTORY)

    def action_focus_command(self) -> None:
        self._query("#command-input", Input).focus()

    def show_screen(self, screen: ScreenId) -> None:
        self._query("#views", ContentSwitcher).current = screen.value
        self._query("#main", Vertical).border_title = _SCREEN_TITLES[screen]

    def write_activity(self, line: str) -> None:
        self.activity_lines.append(line)
        if len(self.activity_lines) > 1000:
            del self.activity_lines[:-1000]
        if self.is_mounted:
            self._query("#activity-log", RichLog).write(line)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-input":
            return
        text = event.value
        if not self._ui_alive():
            return
        try:
            event.input.value = ""
        except ScreenStackError:
            return
        if not self._ui_alive():
            return
        await self.command_from_ui(text)

    async def command_from_ui(self, text: str) -> None:
        if not self._ui_alive():
            return
        result = await run_command_text(self.service, text)
        for line in result.lines:
            self.write_activity(line)
        if result.quiet is not None:
            self.quiet = result.quiet
            self._render_character()
        if result.screen is not None:
            self.show_screen(result.screen)
        await self.refresh_ui()
        self.command_count += 1

    def _on_service_event(self, event: ServiceEvent) -> None:
        del event
        if self._closing or not self.is_running:
            return
        self.call_later(self._enqueue_refresh)

    def _enqueue_refresh(self) -> None:
        if self._closing:
            return
        if self._refresh_running:
            self._refresh_again = True
            return
        self._refresh_running = True
        self.run_worker(self._refresh_loop(), group="refresh", exclusive=False)

    async def _refresh_loop(self) -> None:
        try:
            while not self._closing:
                self._refresh_again = False
                await self.refresh_ui()
                if not self._refresh_again:
                    return
        finally:
            self._refresh_running = False
            if self._refresh_again and not self._closing:
                self.call_later(self._enqueue_refresh)

    async def refresh_ui(self) -> None:
        async with self._refresh_lock:
            await self._refresh_locked()

    async def _refresh_locked(self) -> None:
        if self._closing or not self.is_mounted:
            return
        try:
            await self._refresh_contents()
        except NoMatches:
            return

    async def _refresh_contents(self) -> None:
        connection = self.service.connection_status()
        try:
            projects = await self.service.list_projects()
            selected = await self.service.get_selected_project()
            plan = await self.service.get_run_plan()
            tasks = await self.service.list_tasks()
            jobs = await self.service.list_jobs()
            cases = await self.service.list_error_cases()
            resolutions = await self.service.list_resolutions()
            lab_status = await self.service.lab_status()
        except LabError as exc:
            self._query(WorkspaceView).apply_plan(None, unavailable=exc.message)
            self._query(LabView).apply(empty_lab_status())
            self._set_header(None, connection)
            self._set_character(CharacterState.DISCONNECTED)
            return

        workspace = self._query(WorkspaceView)
        workspace.apply_projects(projects, selected)
        workspace.apply_tasks(tasks, plan.task.id)
        workspace.apply_plan(plan)
        workspace.apply_jobs(jobs)
        selected_job = workspace.selected_job()
        output = []
        if selected_job is not None:
            output = await self.service.get_job_output(selected_job.id)
        workspace.apply_output(selected_job, output)

        preferred_job_id = self.pending_review_job_id
        self.pending_review_job_id = None
        self._query(ReviewView).apply(cases, preferred_job_id=preferred_job_id)
        self._query(LabView).apply(lab_status)

        history = self._query(HistoryView)
        hits: list[SearchHit] = []
        notice = "검색어를 입력하세요. 예: 5432, 403, email, job-0001"
        query = history.query_text.strip()
        if query:
            try:
                hits = await self.service.search_history(query)
                notice = ""
            except LabError as exc:
                notice = exc.message
        history.apply(jobs, cases, resolutions, hits, notice)

        self._set_header(selected, connection)
        self._set_character(
            derive_character_state(
                connection=connection,
                jobs=jobs,
                error_cases=cases,
                lab=lab_status,
            )
        )

    def _tick(self) -> None:
        if self._closing or not self.is_mounted:
            return
        try:
            workspace = self._query(WorkspaceView)
            workspace.tick(datetime.now(timezone.utc))
            lab = self._query(LabView)
        except NoMatches:
            return
        if not self._remote_work_pending(workspace, lab):
            self._poll_ticks = 0
            return
        self._poll_ticks += 1
        if self._poll_ticks >= 2:
            self._poll_ticks = 0
            self._enqueue_refresh()

    def _remote_work_pending(self, workspace: WorkspaceView, lab: LabView) -> bool:
        if any(job.status in ACTIVE_JOB_STATUSES for job in workspace.jobs()):
            return True
        status = lab.status()
        return status is not None and status.active_run_status in {"QUEUED", "RUNNING"}

    def _set_header(self, project: Project | None, connection: ConnectionStatus) -> None:
        del connection
        name = project.name if project is not None else "없음"
        self._query("#top-bar", Static).update(
            format_header(
                project_name=name,
                mode=self.config.mode,
                connection_label=self.service.connection_label(),
            )
        )

    def _set_character(self, state: CharacterState) -> None:
        self._character_state = state
        self._render_character()

    def _render_character(self) -> None:
        if not self.is_mounted:
            return
        self._query(CharacterPanel).show(
            name=self.config.character_name,
            state=self._character_state,
            mode=self.config.mode,
            quiet=self.quiet,
            connected=self.service.connection_status() is ConnectionStatus.CONNECTED,
            worker_connected=self.service.worker_connected(),
        )
