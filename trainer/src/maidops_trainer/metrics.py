"""테스트 분할의 혼동행렬로 macro F1을 계산한다.

정책 이름은 supported-class-macro-f1-v2다.
행은 실제 라벨, 열은 예측 라벨이고 순서는 LABELS와 같다.

support는 그 행의 합, 곧 TP+FN이다. predicted_count는 그 열의 합, 곧 TP+FP다.
support가 0보다 크면 macro 평균에 넣는다. 이때 예측이 한 번도 없으면
precision, recall, F1은 모두 0이다.
support가 0이면 macro에서 뺀다. 예측만 있으면 precision은 0이고 recall과 F1은 null이다.
FP와 predicted_count는 그 경우에도 남긴다.
실제 표본이 하나도 없거나 표본 있는 클래스가 2개 미만이면 평가하지 않는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

METRIC_POLICY = "supported-class-macro-f1-v2"
LABELS: tuple[str, ...] = (
    "DB_CONNECTION",
    "AUTH_PERMISSION",
    "EXTERNAL_NETWORK",
    "INPUT_VALIDATION",
    "OTHER",
)


@dataclass(frozen=True)
class ClassScore:
    label: str
    precision: float | None
    recall: float | None
    f1: float | None
    support: int
    predicted_count: int = 0
    false_positives: int = 0
    included_in_macro: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "support": self.support,
            "predicted_count": self.predicted_count,
            "false_positives": self.false_positives,
            "included_in_macro": self.included_in_macro,
        }


@dataclass(frozen=True)
class MetricReport:
    macro_f1: float
    per_class: tuple[ClassScore, ...]
    confusion: tuple[tuple[int, ...], ...]
    metric_policy: str = METRIC_POLICY

    def per_class_payload(self) -> list[dict[str, object]]:
        return [score.as_dict() for score in self.per_class]

    def confusion_payload(self) -> list[list[int]]:
        return [list(row) for row in self.confusion]

    def included_labels(self) -> list[str]:
        return [score.label for score in self.per_class if score.included_in_macro]

    def evaluation_sample_count(self) -> int:
        return sum(score.support for score in self.per_class)


def confusion_matrix(y_true: list[int], y_pred: list[int], size: int = len(LABELS)) -> list[list[int]]:
    matrix = [[0 for _ in range(size)] for _ in range(size)]
    for truth, predicted in zip(y_true, y_pred, strict=True):
        matrix[truth][predicted] += 1
    return matrix


def evaluate(y_true: list[int], y_pred: list[int]) -> MetricReport:
    return from_confusion(confusion_matrix(y_true, y_pred))


def from_confusion(matrix: list[list[int]]) -> MetricReport:
    size = len(LABELS)
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise ValueError("혼동행렬은 라벨 수와 같은 정사각 행렬이어야 합니다.")
    support = [sum(row) for row in matrix]
    predicted = [sum(matrix[row][column] for row in range(size)) for column in range(size)]
    if sum(support) == 0:
        raise ValueError("실제 표본이 없어 macro F1을 계산할 수 없습니다. 점수를 만들지 않습니다.")
    scores: list[ClassScore] = []
    included: list[float] = []
    for index, label in enumerate(LABELS):
        if any(value < 0 for value in matrix[index]):
            raise ValueError("혼동행렬에는 음수를 넣을 수 없습니다.")
        true_positive = matrix[index][index]
        false_positives = predicted[index] - true_positive
        if support[index] > 0:
            recall = true_positive / support[index]
            precision = 0.0 if predicted[index] == 0 else true_positive / predicted[index]
            f1 = _f1(precision, recall)
            _require_finite(precision, recall, f1)
            included.append(f1)
            scores.append(
                ClassScore(label, precision, recall, f1, support[index], predicted[index], false_positives, True)
            )
        else:
            precision = None if predicted[index] == 0 else 0.0
            if precision is not None:
                _require_finite(precision)
            scores.append(
                ClassScore(label, precision, None, None, 0, predicted[index], false_positives, False)
            )
    if len(included) < 2:
        raise ValueError("macro F1을 계산할 실제 표본 클래스가 2개 미만입니다. 점수를 만들지 않습니다.")
    macro = sum(included) / len(included)
    _require_finite(macro)
    return MetricReport(
        macro_f1=macro,
        per_class=tuple(scores),
        confusion=tuple(tuple(row) for row in matrix),
    )


def _f1(precision: float, recall: float) -> float:
    denominator = precision + recall
    if denominator == 0.0:
        return 0.0
    return (2.0 * precision * recall) / denominator


def _require_finite(*values: float) -> None:
    if any(not math.isfinite(value) for value in values):
        raise ValueError("평가 점수가 유한하지 않습니다. 점수를 만들지 않습니다.")
