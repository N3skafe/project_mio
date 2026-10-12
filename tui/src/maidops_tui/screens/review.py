"""Review. 세션 오류 사례의 라벨을 승인, 수정, 보류한다."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input, Select, Static

from maidops_tui.domain.errors import LabError, format_lab_error
from maidops_tui.domain.models import ErrorCase, ErrorLabel, LabelSource, ReviewDecision, ReviewStatus
from maidops_tui.widgets.host import ops_app


class ReviewView(Vertical):
    def __init__(self) -> None:
        super().__init__(id="review")
        self.selected_case_id: str | None = None
        self._cases: dict[str, ErrorCase] = {}
        self._signature: tuple[tuple[str, str, str], ...] | None = None
        self._shown_case_id: str | None = None
        self._syncing = False

    def compose(self) -> ComposeResult:
        yield Static("Review", classes="view-title", markup=False)
        yield Static(
            "실패 로그의 예측 초안입니다. 확정 라벨은 승인 또는 수정 뒤에만 기록되며, 라벨을 바꿔도 학습은 시작되지 않습니다.",
            id="review-intro",
            markup=False,
        )
        with Horizontal(id="review-body"):
            yield DataTable(id="error-table", cursor_type="row", show_row_labels=False, zebra_stripes=True)
            with VerticalScroll(id="review-detail"):
                yield Static("오류 사례를 선택하세요.", id="error-text", markup=False)
                yield Static("", id="label-info", markup=False)
                yield Select(
                    [(label.value, label.value) for label in ErrorLabel],
                    value=ErrorLabel.OTHER.value,
                    allow_blank=False,
                    id="label-select",
                )
                with Horizontal(id="review-actions"):
                    yield Button("승인", id="approve-button", compact=True)
                    yield Button("수정", id="revise-button", compact=True)
                    yield Button("보류", id="defer-button", compact=True)
                yield Input(placeholder="원인", id="cause-input")
                yield Input(placeholder="해결 방법", id="method-input")
                yield Button("해결 기록 저장", id="save-resolution-button", compact=True)
                yield Static("", id="revision-history", markup=False)

    def on_mount(self) -> None:
        table = self.query_one("#error-table", DataTable)
        table.add_column("사례", key="case")
        table.add_column("라벨", key="label")
        table.add_column("상태", key="status")

    def apply(self, cases: list[ErrorCase], preferred_job_id: str | None = None) -> None:
        self._cases = {case.id: case for case in cases}
        if preferred_job_id is not None:
            match = next((case for case in cases if case.job_id == preferred_job_id), None)
            if match is not None:
                self.selected_case_id = match.id
        if self.selected_case_id not in self._cases:
            self.selected_case_id = cases[-1].id if cases else None
        signature = tuple((case.id, _label_name(case.current_label), case.review_status.value) for case in cases)
        table = self.query_one("#error-table", DataTable)
        if signature != self._signature:
            self._signature = signature
            self._syncing = True
            try:
                table.clear()
                for case in cases:
                    table.add_row(case.id, _label_name(case.current_label), case.review_status.value, key=case.id)
                if self.selected_case_id is not None and cases:
                    table.move_cursor(row=table.get_row_index(self.selected_case_id))
            finally:
                self._syncing = False
        self._show_selected()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self._syncing or event.data_table.id != "error-table" or event.row_key.value is None:
            return
        self.selected_case_id = event.row_key.value
        self._show_selected()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id not in {
            "approve-button",
            "revise-button",
            "defer-button",
            "save-resolution-button",
        }:
            return
        event.stop()
        app = ops_app(self)
        if self.selected_case_id is None:
            app.write_activity("오류: 검토할 오류 사례가 없습니다. 실패한 가상 테스트를 먼저 실행하세요.")
            return
        if button_id == "save-resolution-button":
            cause = self.query_one("#cause-input", Input).value
            method = self.query_one("#method-input", Input).value
            try:
                record = await app.service.save_resolution(self.selected_case_id, cause, method)
            except LabError as exc:
                _write_action_error(app, exc)
                return
            app.write_activity(
                f"해결 기록을 저장했습니다: {record.id} [{record.origin.value}]. 학습은 시작하지 않습니다."
            )
            await app.refresh_ui()
            return
        decision = {
            "approve-button": ReviewDecision.APPROVE,
            "revise-button": ReviewDecision.REVISE,
            "defer-button": ReviewDecision.DEFER,
        }[button_id]
        label = None
        if decision is ReviewDecision.REVISE:
            raw_label = self.query_one("#label-select", Select).value
            try:
                label = ErrorLabel(str(raw_label))
            except ValueError:
                app.write_activity("오류: 수정할 라벨을 선택하세요.")
                return
        try:
            case = await app.service.review_error_case(self.selected_case_id, decision, label)
        except LabError as exc:
            _write_action_error(app, exc)
            return
        app.write_activity(
            f"{case.id} 검토 결과: {case.review_status.value} {_label_name(case.current_label)}. 학습은 시작하지 않습니다."
        )
        await app.refresh_ui()

    def _show_selected(self) -> None:
        case = self._cases.get(self.selected_case_id or "")
        text = self.query_one("#error-text", Static)
        info = self.query_one("#label-info", Static)
        history = self.query_one("#revision-history", Static)
        if case is None:
            text.update("표시할 오류 사례가 없습니다. Workspace에서 실패하는 가상 테스트를 실행하세요.")
            info.update("초안 생성 방식: 없음")
            history.update("")
            self._shown_case_id = None
            return
        text.update(f"원본 오류 텍스트\n{case.raw_text}")
        info.update("\n".join(_label_lines(case)))
        history.update(_format_revisions(case))
        pending = case.draft_label is None
        for button_id in ("approve-button", "revise-button", "defer-button", "save-resolution-button"):
            self.query_one(f"#{button_id}", Button).disabled = pending
        if case.id != self._shown_case_id:
            self._shown_case_id = case.id
            self.query_one("#label-select", Select).value = (
                ErrorLabel.OTHER.value if case.current_label is None else case.current_label.value
            )
            self.query_one("#cause-input", Input).value = ""
            self.query_one("#method-input", Input).value = ""


def _label_name(label: ErrorLabel | None) -> str:
    return "대기" if label is None else label.value


def _label_lines(case: ErrorCase) -> list[str]:
    confirmed = "없음" if case.confirmed_label is None else case.confirmed_label.value
    draft = "없음. 기본 모델의 초안을 기다리는 중입니다." if case.draft_label is None else case.draft_label.value
    return [
        f"예측 초안: {draft}",
        _source_line(case),
        f"확정 라벨: {confirmed}",
        "확정 라벨은 승인 또는 수정된 사례만 기록합니다.",
        f"검토 상태: {case.review_status.value}",
        f"연결된 작업: {case.job_id}",
    ]


def _source_line(case: ErrorCase) -> str:
    if case.draft_source is LabelSource.RULE_BASED:
        version = case.rule_version or "알 수 없음"
        keyword = case.matched_keyword or "없음"
        return (
            f"생성 방식: RULE_BASED (규칙 기반 초안, 규칙 버전 {version}, "
            f"일치 키워드 {keyword}. 모델 추론이 아니며 정답 확률이 아닙니다.)"
        )
    if case.draft_source is LabelSource.FIXTURE:
        return "생성 방식: FIXTURE (가상 fixture, 규칙 기반 분류와 모델 추론이 아닙니다.)"
    if case.draft_source is LabelSource.LOG:
        return "생성 방식: LOG (실행 로그만 저장한 초안입니다.)"
    if case.draft_source is LabelSource.MODEL:
        model = case.model_version_id or "알 수 없음"
        if case.draft_label is None:
            return f"생성 방식: MODEL ({model} 초안을 기다리는 중입니다. 점수와 정답 확률은 없습니다.)"
        return (
            f"생성 방식: MODEL ({model}의 argmax 초안입니다. "
            "softmax 출력은 보정된 정답 확률이 아니며, 학습 평가 점수와 별개입니다.)"
        )
    return f"생성 방식: {case.draft_source.value}"


def _format_revisions(case: ErrorCase) -> str:
    lines = ["라벨 변경 이력"]
    for index, revision in enumerate(case.revisions, start=1):
        stamp = revision.at.strftime("%H:%M:%S")
        lines.append(
            f"{index}. {stamp}Z {revision.review_status.value} "
            f"{revision.label.value} source={revision.source.value} {revision.note}"
        )
    if case.review_status is ReviewStatus.DEFERRED:
        lines.append("이 사례는 보류 상태이므로 확정 학습 데이터에 넣지 않습니다.")
    return "\n".join(lines)


def _write_action_error(app, exc: LabError) -> None:
    for line in format_lab_error(exc):
        app.write_activity(line)
