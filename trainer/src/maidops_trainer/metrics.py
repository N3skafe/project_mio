"""테스트 분할의 혼동행렬로 macro F1을 계산한다.

지원 사례가 없는 클래스의 F1은 None이고 macro 평균에 넣지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

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

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "support": self.support,
        }


@dataclass(frozen=True)
class MetricReport:
    macro_f1: float
    per_class: tuple[ClassScore, ...]
    confusion: tuple[tuple[int, ...], ...]

    def per_class_payload(self) -> list[dict[str, object]]:
        return [score.as_dict() for score in self.per_class]

    def confusion_payload(self) -> list[list[int]]:
        return [list(row) for row in self.confusion]


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
    scores: list[ClassScore] = []
    included: list[float] = []
    for index, label in enumerate(LABELS):
        if any(value < 0 for value in matrix[index]):
            raise ValueError("혼동행렬에는 음수를 넣을 수 없습니다.")
        true_positive = matrix[index][index]
        precision = None if predicted[index] == 0 else true_positive / predicted[index]
        recall = None if support[index] == 0 else true_positive / support[index]
        f1 = None
        if precision is not None and recall is not None:
            denominator = precision + recall
            f1 = 0.0 if denominator == 0 else (2 * precision * recall) / denominator
        if support[index] > 0 and f1 is not None:
            included.append(f1)
        scores.append(ClassScore(label, precision, recall, f1, support[index]))
    if len(included) < 2:
        raise ValueError("macro F1을 계산할 테스트 클래스가 2개 미만입니다.")
    return MetricReport(
        macro_f1=sum(included) / len(included),
        per_class=tuple(scores),
        confusion=tuple(tuple(row) for row in matrix),
    )
