"""설정 로더 테스트."""

from __future__ import annotations

import pytest

from maidops_tui.config import load_config
from maidops_tui.domain.errors import ConfigError
from maidops_tui.domain.models import RunMode


def test_defaults_when_environment_is_empty() -> None:
    config = load_config(environ={}, load_dotenv_file=False)
    assert config.mode is RunMode.DEMO
    assert config.character_name == "미오"
    assert config.quiet is False
    assert config.log_limit == 200
    assert config.demo_delay_seconds == 5.0
    assert config.backend_url == "http://127.0.0.1:8080"


def test_environment_overrides_dotenv(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MAIDOPS_MODE=LIVE\nMAIDOPS_CHARACTER_NAME=파일이름\nMAIDOPS_QUIET=on\n",
        encoding="utf-8",
    )
    config = load_config(
        environ={"MAIDOPS_MODE": "DEMO", "UNRELATED": "secret"},
        dotenv_path=env_file,
    )
    assert config.mode is RunMode.DEMO
    assert config.character_name == "파일이름"
    assert config.quiet is True


def test_invalid_mode_is_rejected() -> None:
    with pytest.raises(ConfigError) as caught:
        load_config(environ={"MAIDOPS_MODE": "LVE"}, load_dotenv_file=False)
    assert "MAIDOPS_MODE" in caught.value.message
    assert caught.value.example == "MAIDOPS_MODE=DEMO"
