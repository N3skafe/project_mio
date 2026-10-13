"""로그에 남기기 전에 비밀처럼 보이는 토큰을 가린다.

적용 위치는 워커가 이벤트를 큐에 넣기 전과, 예외 문구를 SYSTEM 줄로 만들기 전이다.
서버와 TUI는 저장된 문자열을 다시 해석하지 않는다.

지원하는 형태:
- scheme://user:password@host. 비밀번호는 첫 @ 앞의 userinfo다.
- jdbc: 접두가 붙은 같은 URI
- password, passwd, secret, api_key, token 대입
- Bearer 토큰

비밀번호에 @나 공백이 있으면 percent-encoding이 아닌 한 일부만 가리거나 놓칠 수 있다.
모든 비밀 형식을 제거하지는 않는다.
"""

from __future__ import annotations

import re

_URI_USERINFO = re.compile(r"(?i)([a-z][a-z0-9+.-]*://[^/\s:@]*:)([^@\s]+)@")
_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b(\s*[=:]\s*)(\S+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")


def mask_secrets(line: str) -> str:
    masked = _URI_USERINFO.sub(r"\1[REDACTED]@", line)
    masked = _ASSIGNMENT.sub(r"\1\2[REDACTED]", masked)
    return _BEARER.sub("Bearer [REDACTED]", masked)
