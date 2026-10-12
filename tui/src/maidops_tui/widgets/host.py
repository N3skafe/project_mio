"""화면 위젯에서 MaidOpsApp 메서드를 호출할 때 순환 import를 피한다."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widget import Widget

if TYPE_CHECKING:
    from maidops_tui.app import MaidOpsApp


def ops_app(widget: Widget) -> MaidOpsApp:
    from maidops_tui.app import MaidOpsApp

    app = widget.app
    if not isinstance(app, MaidOpsApp):
        raise RuntimeError("MaidOps Lab 화면은 MaidOpsApp 안에서만 동작합니다.")
    return app
