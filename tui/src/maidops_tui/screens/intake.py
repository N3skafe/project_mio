"""LIVE 전용 등록과 실패 로그 가져오기 폼."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static, TextArea


class IntakeScreen(ModalScreen[dict[str, str] | None]):
    BINDINGS = [Binding("escape", "cancel", "닫기", priority=True)]
    DEFAULT_CSS = """
    IntakeScreen {
        align: center middle;
    }
    """

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "intake-cancel":
            self.dismiss(None)
            return
        if event.button.id != "intake-save":
            return
        form = self._collect()
        if form is None:
            return
        self.dismiss(form)

    def _collect(self) -> dict[str, str] | None:
        return None


class ProjectIntakeScreen(IntakeScreen):
    def compose(self) -> ComposeResult:
        with Vertical(id="intake-dialog"):
            yield Static("프로젝트 등록. 신뢰하는 workspace만 등록합니다.", markup=False)
            yield Input(placeholder="id  예: my-api", id="intake-id")
            yield Input(placeholder="이름", id="intake-name")
            yield Input(placeholder="설명. 비워 두면 안내 문장을 저장합니다.", id="intake-summary")
            yield Button("등록", id="intake-save", compact=True)
            yield Button("닫기", id="intake-cancel", compact=True)

    def _collect(self) -> dict[str, str] | None:
        project_id = self.query_one("#intake-id", Input).value.strip()
        name = self.query_one("#intake-name", Input).value.strip()
        if not project_id or not name:
            self.query_one("#intake-dialog Static", Static).update("id와 이름이 필요합니다. 예: my-api / 내 API")
            return None
        return {
            "id": project_id,
            "name": name,
            "summary": self.query_one("#intake-summary", Input).value.strip(),
        }


class TaskIntakeScreen(IntakeScreen):
    def compose(self) -> ComposeResult:
        with Vertical(id="intake-dialog"):
            yield Static("작업 등록. 첫 실행 토큰은 {python}만 허용합니다.", markup=False)
            yield Input(placeholder="id  예: my-check", id="intake-id")
            yield Input(placeholder="이름", id="intake-name")
            yield Input(placeholder="계획", id="intake-plan")
            yield Input(placeholder="relative_workdir  예: sample", id="intake-workdir")
            yield Input(placeholder="스크립트 파일  예: pass_check.py", id="intake-script")
            yield Input(placeholder="timeout_seconds  1-120", id="intake-timeout", value="10")
            yield Button("등록", id="intake-save", compact=True)
            yield Button("닫기", id="intake-cancel", compact=True)

    def _collect(self) -> dict[str, str] | None:
        timeout = self.query_one("#intake-timeout", Input).value.strip()
        if not timeout.isdigit() or not 1 <= int(timeout) <= 120:
            self.query_one("#intake-dialog Static", Static).update("timeout_seconds는 1 이상 120 이하여야 합니다.")
            return None
        values = {
            "id": self.query_one("#intake-id", Input).value.strip(),
            "name": self.query_one("#intake-name", Input).value.strip(),
            "plan_text": self.query_one("#intake-plan", Input).value.strip(),
            "relative_workdir": self.query_one("#intake-workdir", Input).value.strip(),
            "script": self.query_one("#intake-script", Input).value.strip(),
            "timeout_seconds": timeout,
        }
        if not all(values[key] for key in ("id", "name", "plan_text", "relative_workdir", "script")):
            self.query_one("#intake-dialog Static", Static).update("id, 이름, 계획, 상대 경로, 스크립트가 필요합니다.")
            return None
        return values


class ImportLogScreen(IntakeScreen):
    def __init__(self, project_id: str) -> None:
        super().__init__()
        self._project_id = project_id

    def compose(self) -> ComposeResult:
        with Vertical(id="intake-dialog"):
            yield Static("실패 로그 가져오기. 작업을 만들지 않습니다.", markup=False)
            yield Input(placeholder="project_id", id="intake-project", value=self._project_id)
            yield Input(placeholder="출처 힌트. 선택", id="intake-hint")
            yield TextArea(id="intake-log")
            yield Button("가져오기", id="intake-save", compact=True)
            yield Button("닫기", id="intake-cancel", compact=True)

    def _collect(self) -> dict[str, str] | None:
        project_id = self.query_one("#intake-project", Input).value.strip()
        raw_log = self.query_one("#intake-log", TextArea).text.strip()
        if not project_id or not raw_log:
            self.query_one("#intake-dialog Static", Static).update("프로젝트 id와 실패 로그가 필요합니다.")
            return None
        return {
            "project_id": project_id,
            "raw_log": raw_log,
            "source_hint": self.query_one("#intake-hint", Input).value.strip(),
        }
