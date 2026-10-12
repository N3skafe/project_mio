"""설정에 맞는 서비스 구현을 고른다."""

from __future__ import annotations

from maidops_tui.config import AppConfig
from maidops_tui.domain.errors import ConfigError
from maidops_tui.domain.models import RunMode
from maidops_tui.services.api_service import ApiService
from maidops_tui.services.demo_service import DemoService
from maidops_tui.services.protocol import LabService


def build_service(config: AppConfig) -> LabService:
    if config.mode is RunMode.DEMO:
        return DemoService(
            delay_seconds=config.demo_delay_seconds,
            log_limit=config.log_limit,
        )
    if config.mode is RunMode.LIVE:
        return ApiService(config.backend_url)
    raise ConfigError(f"지원하지 않는 실행 모드입니다: {config.mode.value}", "MAIDOPS_MODE=DEMO")
