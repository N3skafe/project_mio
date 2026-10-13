"""평가 정의와 규칙 초안. 학습 성공과 점수 정의를 구분한다."""

from __future__ import annotations

import pytest

from maidops_trainer.metrics import from_confusion
from maidops_trainer.rules import classify_failure


def test_supported_class_with_no_predictions_lowers_macro_f1() -> None:
    """테스트에 있는 클래스를 한 번도 예측하지 않으면 그 클래스의 F1은 0이고 macro에 들어간다.

    행 순서는 DB, AUTH, EXTERNAL, INPUT, OTHER.
    DB 2건과 AUTH 2건은 맞힌다. INPUT 2건은 EXTERNAL로만 예측한다.
    기대 macro F1은 (1 + 1 + 0) / 3 이다.
    """
    report = from_confusion(
        [
            [2, 0, 0, 0, 0],
            [0, 2, 0, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 2, 0, 0],
            [0, 0, 0, 0, 0],
        ]
    )
    input_score = report.per_class[3]
    assert input_score.support == 2
    assert input_score.f1 == 0.0
    assert report.macro_f1 == pytest.approx(2 / 3)


def test_digits_touching_status_codes_do_not_match_auth() -> None:
    assert classify_failure("code 14013 boom").label == "OTHER"
    assert classify_failure("status 403 from the api").label == "AUTH_PERMISSION"


def test_keyword_priority_prefers_auth_over_database() -> None:
    draft = classify_failure("permission denied while opening the database")
    assert draft.label == "AUTH_PERMISSION"
    assert draft.matched_keyword == "permission denied"
