"""환경 변수와 선택적 .env에서 PHASE 1 설정을 읽는다.

비밀 값을 만들지 않는다. 백엔드 주소는 저장만 하고 PHASE 1에서는 접속하지 않는다.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from maidops_tui.domain.errors import ConfigError
from maidops_tui.domain.models import RunMode

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class AppConfig:
    mode: RunMode = RunMode.DEMO
    backend_url: str = "http://127.0.0.1:8080"
    character_name: str = "미오"
    quiet: bool = False
    log_limit: int = 200
    demo_delay_seconds: float = 5.0


def load_config(
    *,
    environ: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
    load_dotenv_file: bool = True,
) -> AppConfig:
    merged: dict[str, str] = {}
    if load_dotenv_file:
        path = dotenv_path if dotenv_path is not None else Path.cwd() / ".env"
        if path.is_file():
            merged.update(_read_env_file(path))
    source = os.environ if environ is None else environ
    for key, value in source.items():
        if key.startswith("MAIDOPS_"):
            merged[key] = value
    return _config_from_mapping(merged)


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise ConfigError(
                f".env {line_number}행에 '='가 없습니다.",
                "MAIDOPS_MODE=DEMO",
            )
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key.startswith("MAIDOPS_"):
            continue
        values[key] = value
    return values


def _config_from_mapping(values: Mapping[str, str]) -> AppConfig:
    mode_text = values.get("MAIDOPS_MODE", RunMode.DEMO.value).strip().upper()
    try:
        mode = RunMode(mode_text)
    except ValueError as exc:
        raise ConfigError(
            f"MAIDOPS_MODE 값이 올바르지 않습니다: {mode_text}",
            "MAIDOPS_MODE=DEMO",
        ) from exc

    backend_url = values.get("MAIDOPS_BACKEND_URL", "http://127.0.0.1:8080").strip()
    if not backend_url:
        raise ConfigError("MAIDOPS_BACKEND_URL이 비어 있습니다.", "http://127.0.0.1:8080")

    name = values.get("MAIDOPS_CHARACTER_NAME", "미오").strip()
    if not name or len(name) > 24:
        raise ConfigError(
            "캐릭터 이름은 1자 이상 24자 이하여야 합니다.",
            "MAIDOPS_CHARACTER_NAME=미오",
        )

    quiet = _parse_bool(values.get("MAIDOPS_QUIET", "false"), "MAIDOPS_QUIET")
    log_limit = _parse_int(values.get("MAIDOPS_LOG_LIMIT", "200"), "MAIDOPS_LOG_LIMIT")
    if log_limit < 1 or log_limit > 5000:
        raise ConfigError("MAIDOPS_LOG_LIMIT은 1 이상 5000 이하여야 합니다.", "200")

    delay = _parse_float(
        values.get("MAIDOPS_DEMO_DELAY_SECONDS", "5.0"),
        "MAIDOPS_DEMO_DELAY_SECONDS",
    )
    if delay < 0 or delay > 30:
        raise ConfigError(
            "MAIDOPS_DEMO_DELAY_SECONDS는 0 이상 30 이하여야 합니다.",
            "1.0",
        )

    return AppConfig(
        mode=mode,
        backend_url=backend_url,
        character_name=name,
        quiet=quiet,
        log_limit=log_limit,
        demo_delay_seconds=delay,
    )


def _parse_bool(raw: str, key: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{key} 값이 올바르지 않습니다: {raw}", "false")


def _parse_int(raw: str, key: str) -> int:
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"{key}는 정수여야 합니다: {raw}", "200") from exc


def _parse_float(raw: str, key: str) -> float:
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"{key}는 숫자여야 합니다: {raw}", "5.0") from exc
