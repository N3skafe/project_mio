"""고정 캐릭터 패널. 로그를 지우거나 포커스를 옮기지 않는다."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from maidops_tui.characters.mio import dialogue_for, portrait
from maidops_tui.domain.models import CharacterState, RunMode


class CharacterPanel(Vertical):
    def __init__(self) -> None:
        super().__init__(id="character")

    def compose(self) -> ComposeResult:
        yield Static("", id="character-mode", markup=False)
        yield Static("", id="character-name", markup=False)
        yield Static("", id="character-status", markup=False)
        yield Static("", id="quiet-flag", markup=False)
        yield Static("", id="character-line", markup=False)
        yield Static("", id="character-art", markup=False)

    def show(
        self,
        *,
        name: str,
        state: CharacterState,
        mode: RunMode,
        quiet: bool,
        connected: bool = False,
        worker_connected: bool = False,
    ) -> None:
        if mode is RunMode.DEMO:
            mode_text = "DEMO · 가상 이벤트"
        elif worker_connected:
            mode_text = "LIVE · 워커 연결"
        elif connected:
            mode_text = "LIVE · 실행 워커 없음"
        else:
            mode_text = "LIVE · 백엔드 없음"
        self.query_one("#character-mode", Static).update(mode_text)
        self.query_one("#character-name", Static).update(f"이름: {name}")
        self.query_one("#character-status", Static).update(f"상태: {state.value}")
        quiet_flag = self.query_one("#quiet-flag", Static)
        quiet_flag.update("대사 숨김")
        quiet_flag.display = quiet
        line = self.query_one("#character-line", Static)
        line.update(dialogue_for(state))
        line.display = not quiet
        self.query_one("#character-art", Static).update(portrait(state))
