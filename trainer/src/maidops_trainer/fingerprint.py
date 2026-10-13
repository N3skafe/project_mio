"""테스트 분할 지문. Java EvaluationFingerprint와 같은 문자열을 만든다."""

from __future__ import annotations

import hashlib


def evaluation_fingerprint(rows: list[tuple[str, str, str]]) -> str:
    """각 행은 (id, label, raw_text)다. id로 정렬한 뒤 SHA-256을 한 번 더 한다."""
    lines = [
        f"{example_id}|{label}|{_sha256(text)}"
        for example_id, label, text in sorted(rows, key=lambda item: item[0])
    ]
    return _sha256("\n".join(lines))


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
