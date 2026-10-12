"""실패 로그의 규칙 기반 baseline.

키워드 목록과 우선순위는 Java FailureRuleClassifier, TUI rules.py와 같다.
점수를 만들지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

RULE_VERSION = "rules-1"
_STATUS_CODE = re.compile(r"(?<!\d)(401|403)(?!\d)")
_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "AUTH_PERMISSION",
        (
            "permission denied",
            "access denied",
            "unauthorized",
            "authentication failed",
            "not authorized",
            "forbidden",
            "eacces",
        ),
    ),
    (
        "DB_CONNECTION",
        (
            "postgresql",
            "postgres",
            ":5432",
            "sqlstate",
            "jdbc",
            "database",
        ),
    ),
    (
        "INPUT_VALIDATION",
        (
            "invalid input",
            "required field",
            "illegal argument",
            "missing required",
            "bad request",
            "입력 검증",
            "validation",
        ),
    ),
    (
        "EXTERNAL_NETWORK",
        (
            "temporary failure in name resolution",
            "name or service not known",
            "name resolution",
            "getaddrinfo",
            "network is unreachable",
            "no route to host",
            "connection timed out",
            "connection refused",
            "timed out",
            "timeout",
            "dns",
        ),
    ),
)


@dataclass(frozen=True)
class RuleDraft:
    label: str
    rule_version: str
    matched_keyword: str | None


def classify_failure(text: str) -> RuleDraft:
    haystack = text.casefold()
    status_code = _STATUS_CODE.search(haystack)
    if status_code is not None:
        return RuleDraft("AUTH_PERMISSION", RULE_VERSION, status_code.group(1))
    for label, keywords in _RULES:
        for keyword in keywords:
            if keyword.casefold() in haystack:
                return RuleDraft(label, RULE_VERSION, keyword)
    return RuleDraft("OTHER", RULE_VERSION, None)
