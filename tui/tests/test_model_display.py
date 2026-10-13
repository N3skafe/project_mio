"""평가 정책이 있는 점수와 과거 기록을 화면에 구분한다."""

from maidops_tui.domain.display import format_model_comparison
from maidops_tui.domain.models import ClassScore, ModelSummary
from maidops_tui.screens.lab import _model_label


def _model(**overrides: object) -> ModelSummary:
    values: dict[str, object] = {
        "id": "mv-00000001",
        "training_run_id": "run-1",
        "is_default": False,
        "device": "cpu",
        "macro_f1": 2 / 3,
        "baseline_macro_f1": 0.5,
        "per_class": (ClassScore("DB_CONNECTION", 1.0, 1.0, 1.0, 2, included_in_macro=True),),
        "confusion_matrix": ((2, 0),),
        "baseline_per_class": (),
        "baseline_confusion_matrix": (),
        "probability_note": "softmax 출력은 보정된 정답 확률이 아닙니다.",
    }
    values.update(overrides)
    return ModelSummary(**values)  # type: ignore[arg-type]


def test_verified_score_names_the_supported_class_average() -> None:
    text = format_model_comparison(
        _model(
            metric_policy="supported-class-macro-f1-v2",
            checkpoint_evaluated=True,
            included_labels=("DB_CONNECTION", "AUTH_PERMISSION", "INPUT_VALIDATION"),
        )
    )
    assert "실제 표본이 있는 클래스 기준 macro F1" in text
    assert "정책 미확인" not in text
    label = _model_label(
        _model(metric_policy="supported-class-macro-f1-v2", checkpoint_evaluated=True)
    )
    assert "실제 표본이 있는 클래스 기준 macro F1" in label


def test_legacy_score_is_not_shown_as_the_current_policy() -> None:
    text = format_model_comparison(_model())
    assert "정책 미확인 legacy" in text
    assert "같은 의미로 비교하지 않습니다" in text
    assert "실제 표본이 있는 클래스 기준 macro F1" not in text
