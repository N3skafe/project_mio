"""History. 작업, 오류 사례, 해결 기록과 키워드 검색."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, RichLog, Static

from maidops_tui.domain.display import display_status
from maidops_tui.domain.models import ErrorCase, Job, ResolutionRecord, SearchHit
from maidops_tui.widgets.host import ops_app


class HistoryView(Vertical):
    def __init__(self) -> None:
        super().__init__(id="history")
        self.query_text = ""
        self._rendered = ""

    def compose(self) -> ComposeResult:
        yield Static("History", classes="view-title", markup=False)
        yield Static("작업, 오류 사례, 해결 기록을 키워드로 찾습니다. 의미 검색은 후속 단계입니다.", markup=False)
        with Horizontal(id="history-search-row"):
            yield Input(placeholder="검색어  예: 5432, 403, email", id="history-query")
            yield Button("검색", id="history-search-button", compact=True)
        yield RichLog(id="history-results", wrap=True, markup=False, highlight=False, auto_scroll=False)

    def apply(
        self,
        jobs: list[Job],
        cases: list[ErrorCase],
        resolutions: list[ResolutionRecord],
        hits: list[SearchHit],
        notice: str,
    ) -> None:
        rendered = _render(jobs, cases, resolutions, hits, notice, self.query_text)
        if rendered == self._rendered:
            return
        self._rendered = rendered
        log = self.query_one("#history-results", RichLog)
        log.clear()
        for line in rendered.splitlines():
            log.write(line)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "history-search-button":
            return
        event.stop()
        await self._search(self.query_one("#history-query", Input).value)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "history-query":
            return
        event.stop()
        await self._search(event.value)

    async def _search(self, raw: str) -> None:
        self.query_text = raw.strip()
        await ops_app(self).refresh_ui()


def _render(
    jobs: list[Job],
    cases: list[ErrorCase],
    resolutions: list[ResolutionRecord],
    hits: list[SearchHit],
    notice: str,
    query: str,
) -> str:
    lines = ["세션 작업"]
    if jobs:
        for job in jobs:
            lines.append(
                f"[SESSION] {job.id} {display_status(job.status)} project={job.project_id} task={job.task_id}"
            )
    else:
        lines.append("이번 세션 작업이 없습니다.")
    lines.append("")
    lines.append("세션 오류 사례")
    if cases:
        for case in cases:
            confirmed = "없음" if case.confirmed_label is None else case.confirmed_label.value
            lines.append(
                f"[SESSION] {case.id} 예측 {case.draft_label.value} {case.draft_source.value} "
                f"확정 {confirmed} {case.review_status.value} job={case.job_id}"
            )
    else:
        lines.append("이번 세션 오류 사례가 없습니다.")
    lines.append("")
    lines.append("해결 기록")
    if resolutions:
        for record in resolutions:
            lines.append(
                f"[{record.origin.value}] {record.id} {record.label.value} {record.cause} / {record.method}"
            )
    else:
        lines.append("해결 기록이 없습니다.")
    lines.append("")
    lines.append("키워드 검색")
    if not query:
        lines.append(notice or "검색어를 입력하세요. 예: 5432, 403, email, job-0001")
        return "\n".join(lines)
    lines.append(f"검색어: {query}")
    if not hits:
        lines.append("일치하는 기록이 없습니다.")
        return "\n".join(lines)
    for hit in hits:
        lines.append(f"[{hit.origin.value}] {hit.kind.value} {hit.title} {hit.excerpt}")
    return "\n".join(lines)
