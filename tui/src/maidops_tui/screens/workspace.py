"""Workspace. 프로젝트, 실행 계획, 가상 작업 출력을 보여 준다."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, RichLog, Static
from textual.widgets.data_table import CellDoesNotExist

from maidops_tui.domain.display import display_status, format_elapsed, format_job_meta
from maidops_tui.domain.models import ACTIVE_JOB_STATUSES, Job, JobStatus, OutputLine, Project, RegisteredTask, RunPlan
from maidops_tui.widgets.host import ops_app

_STATUS_STYLE = {
    "PASS": "bold #8fdbb0",
    "FAIL": "bold #f0a0a0",
    "RUNNING": "#9ec1f0",
    "QUEUED": "#9ec1f0",
    "CANCELLED": "#d5d8de",
    "CANCEL_REQUESTED": "#e6c07b",
}


def status_text(status: JobStatus) -> Text:
    word = display_status(status)
    return Text(word, style=_STATUS_STYLE.get(word, ""))


def output_text(line: str) -> Text | str:
    if line in _STATUS_STYLE:
        return Text(line, style=_STATUS_STYLE[line])
    if line.startswith("RESULT FAIL") or "OUTPUT_LIMIT_EXCEEDED" in line or "SUPERVISION_FAILED" in line:
        return Text(line, style="bold #f0a0a0")
    if line.startswith("RESULT "):
        word = line.removeprefix("RESULT ")
        return Text(line, style=_STATUS_STYLE.get(word, "bold"))
    return line


class WorkspaceView(Vertical):
    def __init__(self) -> None:
        super().__init__(id="workspace")
        self.selected_job_id: str | None = None
        self._known_job_ids: set[str] = set()
        self._jobs: dict[str, Job] = {}
        self._project_signature: tuple[tuple[str, bool], ...] | None = None
        self._task_signature: tuple[tuple[str, bool], ...] | None = None
        self._job_signature: tuple[tuple[str, str, bool], ...] | None = None
        self._output_job_id: str | None = None
        self._shown_lines: list[OutputLine] = []
        self._syncing = False

    def compose(self) -> ComposeResult:
        yield Static("Workspace", classes="view-title", markup=False)
        yield Static("", id="run-plan", markup=False)
        yield DataTable(id="task-table", cursor_type="row", show_row_labels=False, zebra_stripes=True)
        yield DataTable(id="project-table", cursor_type="row", show_row_labels=False, zebra_stripes=True)
        yield DataTable(id="jobs-table", cursor_type="row", show_row_labels=False, zebra_stripes=True)
        with Horizontal(id="workspace-actions"):
            yield Button("테스트 실행", id="run-test-button", compact=True)
            yield Button("취소", id="cancel-job-button", compact=True)
            yield Button("실패 사례", id="open-failure-button", compact=True)
        yield Static("작업을 선택하면 출력과 경과 시간이 표시됩니다.", id="job-meta", markup=False)
        yield RichLog(id="job-log", wrap=True, markup=False, highlight=False, auto_scroll=True)

    def on_mount(self) -> None:
        tasks = self.query_one("#task-table", DataTable)
        tasks.add_column("선택", key="mark")
        tasks.add_column("작업", key="task")
        tasks.add_column("이름", key="name")
        projects = self.query_one("#project-table", DataTable)
        projects.add_column("선택", key="mark")
        projects.add_column("프로젝트", key="project")
        projects.add_column("설명", key="summary")
        jobs = self.query_one("#jobs-table", DataTable)
        jobs.add_column("작업", key="job")
        jobs.add_column("상태", key="status")
        jobs.add_column("경과", key="elapsed")

    def apply_projects(self, projects: list[Project], selected: Project | None) -> None:
        signature = tuple((project.id, selected is not None and project.id == selected.id) for project in projects)
        if signature == self._project_signature:
            return
        self._project_signature = signature
        table = self.query_one("#project-table", DataTable)
        self._syncing = True
        try:
            table.clear()
            for project in projects:
                mark = "선택" if selected is not None and project.id == selected.id else ""
                table.add_row(mark, project.id, project.name, key=project.id)
        finally:
            self._syncing = False

    def apply_plan(self, plan: RunPlan | None, unavailable: str | None = None) -> None:
        target = self.query_one("#run-plan", Static)
        if unavailable:
            target.update(unavailable)
            return
        if plan is None:
            target.update("선택된 프로젝트가 없습니다.")
            return
        target.update(plan.describe())

    def apply_tasks(self, tasks: list[RegisteredTask], selected_id: str | None) -> None:
        signature = tuple((task.id, task.id == selected_id) for task in tasks)
        if signature == self._task_signature:
            return
        self._task_signature = signature
        table = self.query_one("#task-table", DataTable)
        self._syncing = True
        try:
            table.clear()
            for task in tasks:
                mark = "선택" if task.id == selected_id else ""
                table.add_row(mark, task.id, task.name, key=task.id)
        finally:
            self._syncing = False

    def apply_jobs(self, jobs: list[Job]) -> None:
        new_ids = [job.id for job in jobs if job.id not in self._known_job_ids]
        self._known_job_ids.update(job.id for job in jobs)
        if new_ids:
            self.selected_job_id = new_ids[-1]
        elif self.selected_job_id not in {job.id for job in jobs}:
            self.selected_job_id = jobs[-1].id if jobs else None
        self._jobs = {job.id: job for job in jobs}
        signature = tuple(
            (job.id, job.status.value, job.output_truncated, job.termination_reason, job.log_storage_incomplete)
            for job in jobs
        )
        table = self.query_one("#jobs-table", DataTable)
        now = datetime.now(timezone.utc)
        if signature != self._job_signature:
            self._job_signature = signature
            self._syncing = True
            try:
                table.clear()
                for job in jobs:
                    table.add_row(
                        job.id,
                        status_text(job.status),
                        format_elapsed(job.elapsed_seconds(now)),
                        key=job.id,
                    )
                if self.selected_job_id is not None and jobs:
                    table.move_cursor(row=table.get_row_index(self.selected_job_id))
            finally:
                self._syncing = False
        elif self.selected_job_id is not None:
            self._update_elapsed_cell(now)

    def apply_output(self, job: Job | None, lines: list[OutputLine]) -> None:
        log = self.query_one("#job-log", RichLog)
        if job is None:
            if self._output_job_id is not None or self._shown_lines:
                log.clear()
            self._output_job_id = None
            self._shown_lines = []
            return
        if not _extends(self._shown_lines, lines) or self._output_job_id != job.id:
            log.clear()
            self._shown_lines = []
            self._output_job_id = job.id
        for line in lines[len(self._shown_lines) :]:
            log.write(output_text(line.text))
        self._shown_lines = list(lines)
        self.query_one("#job-meta", Static).update(format_job_meta(job, datetime.now(timezone.utc)))

    def jobs(self) -> list[Job]:
        return list(self._jobs.values())

    def tick(self, now: datetime) -> None:
        job = self.selected_job()
        if job is None or job.status not in ACTIVE_JOB_STATUSES:
            return
        self.query_one("#job-meta", Static).update(format_job_meta(job, now))
        self._update_elapsed_cell(now)

    def selected_job(self) -> Job | None:
        if self.selected_job_id is None:
            return None
        return self._jobs.get(self.selected_job_id)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id not in {"run-test-button", "cancel-job-button", "open-failure-button"}:
            return
        event.stop()
        app = ops_app(self)
        if button_id == "run-test-button":
            await app.command_from_ui("/test")
            return
        if button_id == "cancel-job-button":
            if self.selected_job_id is None:
                app.write_activity("오류: 취소할 작업을 선택하세요.")
                app.write_activity("예: /cancel job-0001")
                return
            await app.command_from_ui(f"/cancel {self.selected_job_id}")
            return
        job = self.selected_job()
        if job is None or job.status is not JobStatus.FAILED:
            app.write_activity("오류: 실패한 작업을 선택해야 오류 사례로 이동할 수 있습니다.")
            return
        app.pending_review_job_id = job.id
        await app.command_from_ui("/review")

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self._syncing or event.row_key.value is None:
            return
        if event.data_table.id == "task-table":
            await ops_app(self).service.select_task(str(event.row_key.value))
            await ops_app(self).refresh_ui()
            return
        if event.data_table.id == "project-table":
            await ops_app(self).command_from_ui(f"/project select {event.row_key.value}")
            return
        if event.data_table.id == "jobs-table":
            self.selected_job_id = event.row_key.value
            await ops_app(self).refresh_ui()

    def _update_elapsed_cell(self, now: datetime) -> None:
        job = self.selected_job()
        if job is None:
            return
        table = self.query_one("#jobs-table", DataTable)
        if not table.columns:
            return
        try:
            table.update_cell(job.id, "elapsed", format_elapsed(job.elapsed_seconds(now)))
        except CellDoesNotExist:
            return


def _extends(previous: list[OutputLine], current: list[OutputLine]) -> bool:
    if len(current) < len(previous):
        return False
    for left, right in zip(previous, current, strict=False):
        if left.sequence != right.sequence or left.text != right.text:
            return False
    return True
