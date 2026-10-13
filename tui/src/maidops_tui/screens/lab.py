"""Lab. LIVE의 확정 라벨만 학습하고, 조건이 부족하면 점수를 만들지 않는다."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Select, Static

from maidops_tui.domain.display import format_lab_status, format_model_comparison, lab_notice
from maidops_tui.domain.errors import LabError
from maidops_tui.domain.models import LabStatus, ModelSummary
from maidops_tui.widgets.host import ops_app


class LabView(Vertical):
    def __init__(self) -> None:
        super().__init__(id="lab")
        self._status: LabStatus | None = None

    def compose(self) -> ComposeResult:
        yield Static("Lab", classes="view-title", markup=False)
        yield Static("", id="lab-summary", markup=False)
        yield Static("", id="lab-notice", markup=False)
        yield Select([("모델 없음", "none")], id="model-select", allow_blank=False, disabled=True)
        with Horizontal(id="lab-actions"):
            yield Button("학습 시작", id="train-button", disabled=True, compact=True)
            yield Button("평가 비교", id="compare-button", disabled=True, compact=True)
            yield Button("기본 모델 선택", id="select-model-button", disabled=True, compact=True)

    def apply(self, status: LabStatus) -> None:
        self._status = status
        self.query_one("#lab-summary", Static).update(format_lab_status(status))
        self.query_one("#lab-notice", Static).update(lab_notice(status))
        select = self.query_one("#model-select", Select)
        previous = select.value
        if status.models:
            select.set_options([(_model_label(model), model.id) for model in status.models])
            select.disabled = False
            if previous in {model.id for model in status.models}:
                select.value = previous
        else:
            select.set_options([("모델 없음", "none")])
            select.disabled = True
        train = self.query_one("#train-button", Button)
        if status.active_run_status == "QUEUED":
            train.label = "학습 취소"
            train.disabled = False
        elif status.active_run_status == "RUNNING":
            train.label = "학습 시작"
            train.disabled = True
        else:
            train.label = "학습 시작"
            train.disabled = not status.eligible
        self.query_one("#compare-button", Button).disabled = status.latest_model is None
        chosen = _chosen(status, select.value)
        self.query_one("#select-model-button", Button).disabled = chosen is None or chosen.is_default

    def status(self) -> LabStatus | None:
        return self._status

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id not in {"train-button", "compare-button", "select-model-button"}:
            return
        event.stop()
        app = ops_app(self)
        status = self._status
        try:
            if event.button.id == "train-button":
                await self._train(app, status)
            elif event.button.id == "compare-button":
                self._compare(app, status)
            else:
                await self._select(app, status)
        except LabError as exc:
            app.write_activity(exc.message)
        app._enqueue_refresh()

    async def _train(self, app, status: LabStatus | None) -> None:
        if status is not None and status.active_run_status == "QUEUED" and status.active_run_id:
            await app.service.cancel_training(status.active_run_id)
            app.write_activity("대기 중인 학습을 취소했습니다. 자동으로 다시 시작하지 않습니다.")
            return
        run_id = await app.service.start_training()
        app.write_activity(
            f"학습을 대기열에 넣었습니다: {run_id}. 점수는 학습이 끝난 뒤에만 표시합니다. 기본 모델은 바뀌지 않습니다."
        )

    def _compare(self, app, status: LabStatus | None) -> None:
        model = None if status is None else _chosen(status, self.query_one("#model-select", Select).value)
        if model is None and status is not None:
            model = status.latest_model
        if model is None:
            app.write_activity("비교할 평가 결과가 없습니다. 점수를 만들지 않았습니다.")
            return
        app.write_activity(format_model_comparison(model))

    async def _select(self, app, status: LabStatus | None) -> None:
        if status is None:
            app.write_activity("선택할 모델이 없습니다. 점수를 만들지 않았습니다.")
            return
        choice = self.query_one("#model-select", Select).value
        model = _chosen(status, choice)
        if model is None:
            app.write_activity("선택할 모델이 없습니다. 점수를 만들지 않았습니다.")
            return
        if model.is_default:
            app.write_activity(f"{model.id}은 이미 기본 모델입니다.")
            return
        await app.service.select_default_model(model.id)
        app.write_activity(f"기본 모델을 선택했습니다: {model.id}. 학습을 다시 실행하지 않았습니다.")


def _model_label(model: ModelSummary) -> str:
    mark = "기본" if model.is_default else "비교"
    if model.metric_policy == "supported-class-macro-f1-v2" and model.checkpoint_evaluated:
        return f"{mark} {model.id} 실제 표본이 있는 클래스 기준 macro F1 {model.macro_f1:.4f}"
    return f"{mark} {model.id} 정책 미확인 legacy {model.macro_f1:.4f}"


def _chosen(status: LabStatus, value: object) -> ModelSummary | None:
    if value in {None, "none", Select.NULL}:
        return None
    return next((model for model in status.models if model.id == value), None)
