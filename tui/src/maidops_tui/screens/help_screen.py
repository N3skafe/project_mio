"""도움말 모달."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from maidops_tui.commands.help_text import help_lines


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "닫기", priority=True)]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-body"):
            yield Static("\n".join(help_lines()), id="help-text", markup=False)
            yield Button("닫기", id="close-help-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-help-button":
            self.dismiss(None)
