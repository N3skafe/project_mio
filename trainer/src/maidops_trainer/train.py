"""고정 임베딩 위의 MLP를 학습하고 테스트 분할을 한 번만 평가한다."""

from __future__ import annotations

import copy
import hashlib
import pickle
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import torch
from torch import nn

from maidops_trainer.device import TrainError, resolve_device
from maidops_trainer.embedding import EMBEDDING_DIM, EMBEDDING_ID, HashingCharNgramEmbedder
from maidops_trainer.metrics import LABELS, MetricReport, evaluate
from maidops_trainer.rules import classify_failure

LABEL_SCHEMA = "labels-1"
CHECKPOINT_FORMAT = "maidops-mlp-v1"
_LABEL_INDEX = {label: index for index, label in enumerate(LABELS)}


@dataclass(frozen=True)
class TrainingExample:
    example_id: str
    text: str
    label: str
    split: str
    group_key: str


@dataclass(frozen=True)
class TrainResult:
    device: str
    epochs_ran: int
    macro_f1: float
    per_class: list[dict[str, object]]
    confusion: list[list[int]]
    baseline_macro_f1: float
    baseline_per_class: list[dict[str, object]]
    baseline_confusion: list[list[int]]
    checksum_sha256: str
    byte_size: int
    config: dict[str, float | int]


class MlpClassifier(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, num_classes: int, dropout: float) -> None:
        super().__init__()
        self.hidden = nn.Linear(input_dim, hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.output = nn.Linear(hidden_dim, num_classes)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.output(self.dropout(torch.relu(self.hidden(features))))


def train_classifier(
    examples: list[TrainingExample],
    model_path: Path,
    *,
    seed: int = 42,
    hidden_dim: int = 64,
    max_epochs: int = 40,
    batch_size: int = 16,
    learning_rate: float = 1e-2,
    dropout: float = 0.0,
    patience: int = 8,
    device_request: str = "cpu",
    heartbeat: Callable[[], None] | None = None,
) -> TrainResult:
    _assert_groups(examples)
    device = resolve_device(device_request)
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    embedder = HashingCharNgramEmbedder()
    features = {
        split: embedder.embed_batch([item.text for item in examples if item.split == split])
        for split in ("TRAIN", "VAL", "TEST")
    }
    targets = {
        split: torch.tensor(
            [_label_index(item.label) for item in examples if item.split == split],
            dtype=torch.long,
        )
        for split in ("TRAIN", "VAL", "TEST")
    }
    model = MlpClassifier(EMBEDDING_DIM, hidden_dim, len(LABELS), dropout).to(device)
    counts = torch.bincount(targets["TRAIN"], minlength=len(LABELS)).float()
    present = int((counts > 0).sum().item()) or 1
    weights = torch.zeros(len(LABELS), dtype=torch.float32)
    for index, count in enumerate(counts.tolist()):
        if count > 0:
            weights[index] = present / count
    loss_fn = nn.CrossEntropyLoss(weight=weights.to(device))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    best_state = copy.deepcopy(model.state_dict())
    best_score = -1.0
    stale = 0
    epochs_ran = 0
    train_x = features["TRAIN"].to(device)
    train_y = targets["TRAIN"].to(device)
    for epoch in range(max_epochs):
        if heartbeat is not None:
            heartbeat()
        epochs_ran = epoch + 1
        model.train()
        order = torch.randperm(train_x.size(0), generator=generator)
        for start in range(0, train_x.size(0), batch_size):
            batch = order[start : start + batch_size]
            optimizer.zero_grad()
            loss = loss_fn(model(train_x[batch]), train_y[batch])
            loss.backward()
            optimizer.step()
        val_score = _validation_score(targets["VAL"].tolist(), _predict(model, features["VAL"], device))
        if val_score > best_score:
            best_score = val_score
            best_state = copy.deepcopy({key: value.detach().cpu() for key, value in model.state_dict().items()})
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break
    model.load_state_dict(best_state)
    model.to(device)
    test_rows = [item for item in examples if item.split == "TEST"]
    test_true = targets["TEST"].tolist()
    test_pred = _predict(model, features["TEST"], device)
    measured = _measured(test_true, test_pred, "테스트")
    baseline_pred = [_label_index(classify_failure(item.text).label) for item in test_rows]
    baseline = _measured(test_true, baseline_pred, "규칙 baseline")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(_checkpoint(best_state, hidden_dim, dropout, seed), model_path)
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    return TrainResult(
        device=device.type,
        epochs_ran=epochs_ran,
        macro_f1=measured.macro_f1,
        per_class=measured.per_class_payload(),
        confusion=measured.confusion_payload(),
        baseline_macro_f1=baseline.macro_f1,
        baseline_per_class=baseline.per_class_payload(),
        baseline_confusion=baseline.confusion_payload(),
        checksum_sha256=digest,
        byte_size=model_path.stat().st_size,
        config={
            "embedding_dim": EMBEDDING_DIM,
            "hidden_dim": hidden_dim,
            "epochs_ran": epochs_ran,
            "max_epochs": max_epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "dropout": dropout,
            "seed": seed,
        },
    )


def predict_label(model_path: Path, text: str, expected_checksum: str) -> str:
    """저장된 MLP의 argmax만 반환한다. 확률과 평가 점수는 만들지 않는다."""
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if digest != expected_checksum:
        raise TrainError("모델 파일 체크섬이 기록과 다릅니다. 초안을 만들지 않습니다.")
    payload = load_checkpoint(model_path)
    hidden = int(payload["hidden_dim"])
    dropout = float(payload["dropout"])
    state = payload["state_dict"]
    if not isinstance(state, dict):
        raise TrainError("체크포인트에 가중치가 없습니다.")
    model = MlpClassifier(EMBEDDING_DIM, hidden, len(LABELS), dropout)
    model.load_state_dict(state)
    predicted = _predict(model, HashingCharNgramEmbedder().embed_batch([text]), torch.device("cpu"))
    return LABELS[predicted[0]]


def load_checkpoint(path: Path) -> dict[str, object]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, pickle.UnpicklingError) as exc:
        raise TrainError("모델 파일을 열지 못했습니다.") from exc
    if not isinstance(payload, dict) or payload.get("format") != CHECKPOINT_FORMAT:
        raise TrainError("이 연구실의 MLP 체크포인트가 아닙니다.")
    if payload.get("embedding_id") != EMBEDDING_ID or payload.get("label_schema_version") != LABEL_SCHEMA:
        raise TrainError("임베딩 또는 라벨 체계가 다릅니다.")
    return payload


def _measured(y_true: list[int], y_pred: list[int], name: str) -> MetricReport:
    try:
        return evaluate(y_true, y_pred)
    except ValueError as exc:
        raise TrainError(f"{name} 분할에서 macro F1을 계산할 수 없습니다. 점수를 만들지 않습니다.") from exc


def _validation_score(y_true: list[int], y_pred: list[int]) -> float:
    """검증 macro F1. 클래스가 부족하면 후보로 쓰지 않고, 점수로 저장하지 않는다."""
    try:
        return evaluate(y_true, y_pred).macro_f1
    except ValueError:
        return -1.0


def _checkpoint(state: dict[str, torch.Tensor], hidden_dim: int, dropout: float, seed: int) -> dict[str, object]:
    return {
        "format": CHECKPOINT_FORMAT,
        "embedding_id": EMBEDDING_ID,
        "label_schema_version": LABEL_SCHEMA,
        "labels": list(LABELS),
        "embedding_dim": EMBEDDING_DIM,
        "hidden_dim": hidden_dim,
        "dropout": dropout,
        "seed": seed,
        "state_dict": state,
    }


def _predict(model: MlpClassifier, features: torch.Tensor, device: torch.device) -> list[int]:
    model.eval()
    with torch.no_grad():
        logits = model(features.to(device))
        return logits.argmax(dim=1).detach().cpu().tolist()


def _label_index(label: str) -> int:
    try:
        return _LABEL_INDEX[label]
    except KeyError as exc:
        raise TrainError(f"라벨 체계에 없는 값입니다: {label}") from exc


def _assert_groups(examples: list[TrainingExample]) -> None:
    if not examples:
        raise TrainError("학습할 확정 사례가 없습니다. 점수를 만들지 않습니다.")
    seen: dict[str, str] = {}
    counts = {"TRAIN": 0, "VAL": 0, "TEST": 0}
    for example in examples:
        if example.split not in counts:
            raise TrainError(f"알 수 없는 분할입니다: {example.split}")
        counts[example.split] += 1
        previous = seen.get(example.group_key)
        if previous is not None and previous != example.split:
            raise TrainError(
                f"그룹 {example.group_key}가 {previous}와 {example.split}에 함께 있습니다. 학습을 중단합니다."
            )
        seen[example.group_key] = example.split
    if min(counts.values()) < 1:
        raise TrainError("학습, 검증, 테스트 분할이 모두 있어야 합니다. 점수를 만들지 않습니다.")
