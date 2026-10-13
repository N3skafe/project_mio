"""공통 JSON fixture로 macro F1 정의를 확인한다. 언어별 기대값을 따로 두지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maidops_trainer.metrics import LABELS, METRIC_POLICY, from_confusion

FIXTURE = Path(__file__).resolve().parents[2] / "contracts" / "metrics" / "supported-class-macro-f1-v2.json"


def test_shared_fixture_matches_python_metrics() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert document["metric_policy"] == METRIC_POLICY
    assert document["label_order"] == list(LABELS)
    assert document["row_meaning"] == "actual"
    assert document["column_meaning"] == "predicted"
    for case in document["cases"]:
        matrix = case["matrix"]
        if case.get("error") == "label-order":
            report = from_confusion(matrix)
            submitted = [score.label for score in report.per_class]
            assert submitted == list(LABELS)
            assert case["submitted_label_order"] != submitted
            swapped = _scores_in_order(report, case["submitted_label_order"])
            assert [score.label for score in swapped] != submitted
            continue
        if case.get("error"):
            with pytest.raises(ValueError):
                from_confusion(matrix)
            continue
        report = from_confusion(matrix)
        assert report.metric_policy == METRIC_POLICY
        assert report.macro_f1 == pytest.approx(_number(case["macro_f1"]))
        assert report.evaluation_sample_count() == case["evaluation_sample_count"]
        assert report.included_labels() == case["included_labels"]
        by_label = {score.label: score for score in report.per_class}
        for expected in case.get("per_class", []):
            actual = by_label[expected["label"]]
            assert actual.support == expected["support"]
            assert actual.predicted_count == expected["predicted_count"]
            assert actual.false_positives == expected["false_positives"]
            assert actual.included_in_macro is expected["included_in_macro"]
            assert _close(actual.precision, expected["precision"])
            assert _close(actual.recall, expected["recall"])
            assert _close(actual.f1, expected["f1"])


def _scores_in_order(report, order: list[str]):
    by_label = {score.label: score for score in report.per_class}
    return [by_label[label] for label in order]


def _close(actual: float | None, expected: object) -> bool:
    if expected is None:
        return actual is None
    assert actual == pytest.approx(_number(expected))
    return True


def _number(value: object) -> float:
    text = str(value)
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return int(numerator) / int(denominator)
    return float(text)
