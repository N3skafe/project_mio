"""등록 실패 시나리오가 의도한 라벨과 서로 다른 문장을 가지는지 확인한다."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from maidops_tui.domain.rules import classify_failure

_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")
_PATH = re.compile(r"([a-z]:\\[^\s]+)|(/[^\s]+)")
_HEX = re.compile(r"\b[0-9a-f]{8,}\b")
_NUMBER = re.compile(r"\d+")
_SPACE = re.compile(r"\s+")


def _scenarios():
    path = Path(__file__).resolve().parents[2] / "fixtures" / "trusted-projects" / "sample" / "lab_failures.py"
    spec = importlib.util.spec_from_file_location("lab_failures", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SCENARIOS


def _normalize(text: str) -> str:
    value = text.lower()
    value = _UUID.sub("<uuid>", value)
    value = _PATH.sub("<path>", value)
    value = _HEX.sub("<hex>", value)
    value = _NUMBER.sub("<n>", value)
    value = _SPACE.sub(" ", value).strip()
    return value[:500]


def test_lab_failures_match_rules_and_stay_distinct() -> None:
    scenarios = _scenarios()
    assert len(scenarios) == 50
    counts: dict[str, int] = {}
    templates: set[str] = set()
    for key, item in scenarios.items():
        draft = classify_failure(item["stderr"])
        assert draft.label == item["label"], key
        counts[item["label"]] = counts.get(item["label"], 0) + 1
        templates.add(_normalize(item["stderr"]))
    assert counts == {
        "DB_CONNECTION": 10,
        "AUTH_PERMISSION": 10,
        "INPUT_VALIDATION": 10,
        "EXTERNAL_NETWORK": 10,
        "OTHER": 10,
    }
    assert len(templates) == 50
