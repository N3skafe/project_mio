"""로그에 남기기 전에 비밀처럼 보이는 토큰을 가린다."""

from __future__ import annotations

import re

_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b(\s*[=:]\s*)(\S+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")


def mask_secrets(line: str) -> str:
    masked = _ASSIGNMENT.sub(r"\1\2[REDACTED]", line)
    return _BEARER.sub("Bearer [REDACTED]", masked)
