"""도메인·명령·설정에서 공통으로 쓰는 오류."""

from __future__ import annotations


class LabError(Exception):
    """사용자가 볼 수 있는 실패. 앱을 종료하지 않는다."""

    def __init__(self, message: str, example: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.example = example


class CommandSyntaxError(LabError):
    """명시적 명령 문법이 잘못된 경우."""


class NotFoundError(LabError):
    """요청한 식별자가 세션에 없는 경우."""


class StateError(LabError):
    """현재 상태에서는 그 조작을 할 수 없는 경우."""


class LiveModeUnavailable(LabError):
    """LIVE 모드이지만 PHASE 1에는 백엔드 클라이언트가 없는 경우."""


class ConfigError(LabError):
    """설정 값이 잘못된 경우."""


def format_lab_error(error: LabError) -> list[str]:
    lines = [f"오류: {error.message}"]
    if error.example:
        lines.append(f"예: {error.example}")
    return lines
