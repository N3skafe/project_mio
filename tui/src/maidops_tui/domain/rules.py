"""실패 로그의 규칙 기반 초안.

키워드 목록과 우선순위는 Java FailureRuleClassifier와 같게 유지한다.
점수를 만들지 않으며, 일치 키워드는 정답 확률이 아니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from maidops_tui.domain.models import ErrorLabel

RULE_VERSION = "rules-1"

_STATUS_CODE = re.compile(r"(?<!\d)(401|403)(?!\d)")

_RULES: tuple[tuple[ErrorLabel, tuple[str, ...]], ...] = (
    (
        ErrorLabel.AUTH_PERMISSION,
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
        ErrorLabel.DB_CONNECTION,
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
        ErrorLabel.INPUT_VALIDATION,
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
        ErrorLabel.EXTERNAL_NETWORK,
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
    label: ErrorLabel
    rule_version: str
    matched_keyword: str | None


def classify_failure(text: str) -> RuleDraft:
    haystack = text.casefold()
    status_code = _STATUS_CODE.search(haystack)
    if status_code is not None:
        return RuleDraft(ErrorLabel.AUTH_PERMISSION, RULE_VERSION, status_code.group(1))
    for label, keywords in _RULES:
        for keyword in keywords:
            if keyword.casefold() in haystack:
                return RuleDraft(label, RULE_VERSION, keyword)
    return RuleDraft(ErrorLabel.OTHER, RULE_VERSION, None)
