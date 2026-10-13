"""고정 임베딩 위의 MLP를 학습하고 테스트 분할을 한 번만 평가한다.

저장한 파일을 weights_only=True로 다시 연 예측만 평가 점수로 쓴다.
weights_only는 완전한 샌드박스가 아니다. 비신뢰 업로드는 받지 않는다.
"""

from __future__ import annotations

import copy
import hashlib
import json
import pickle
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import torch
from torch import nn

from maidops_trainer.device import TrainError, resolve_device
from maidops_trainer.embedding import EMBEDDING_DIM, EMBEDDING_ID, HashingCharNgramEmbedder
from maidops_trainer.fingerprint import evaluation_fingerprint
from maidops_trainer.metrics import LABELS, METRIC_POLICY, MetricReport, evaluate
from maidops_trainer.rules import classify_failure

LABEL_SCHEMA = "labels-1"
CHECKPOINT_FORMAT_V1 = "maidops-mlp-v1"
CHECKPOINT_FORMAT_V2 = "maidops-mlp-v2"
MAX_CHECKPOINT_BYTES = 8 * 1024 * 1024
_LABEL_INDEX = {label: index for index, label in enumerate(LABELS)}
_STATE_KEYS = ("hidden.weight", "hidden.bias", "output.weight", "output.bias")


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
    metric_policy: str
    label_order: list[str]
    included_labels: list[str]
    evaluation_sample_count: int
    evaluation_fingerprint: str
    training_dataset_fingerprint: str
    checkpoint_evaluated: bool


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
    training_dataset_fingerprint: str = "",
    code_version: str = "unknown",
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
    memory_pred = _predict(model, features["TEST"], device)
    _measured(test_true, memory_pred, "테스트")
    baseline_pred = [_label_index(classify_failure(item.text).label) for item in test_rows]
    baseline = _measured(test_true, baseline_pred, "규칙 baseline")
    fingerprint = evaluation_fingerprint([(item.example_id, item.label, item.text) for item in test_rows])
    _write_checkpoint(
        model_path,
        best_state,
        hidden_dim=hidden_dim,
        dropout=dropout,
        seed=seed,
        training_dataset_fingerprint=training_dataset_fingerprint,
        evaluation_dataset_fingerprint=fingerprint,
        code_version=code_version,
    )
    try:
        reloaded = _model_from_payload(load_checkpoint(model_path))
        reloaded_pred = _predict(reloaded, features["TEST"], torch.device("cpu"))
    except TrainError:
        _discard(model_path)
        raise
    if reloaded_pred != memory_pred:
        _discard(model_path)
        raise TrainError("다시 로드한 체크포인트의 예측이 학습 직후 예측과 다릅니다. 파일을 남기지 않습니다.")
    measured = _measured(test_true, reloaded_pred, "다시 로드한 체크포인트")
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
        metric_policy=measured.metric_policy,
        label_order=list(LABELS),
        included_labels=measured.included_labels(),
        evaluation_sample_count=measured.evaluation_sample_count(),
        evaluation_fingerprint=fingerprint,
        training_dataset_fingerprint=training_dataset_fingerprint,
        checkpoint_evaluated=True,
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


def load_checkpoint(path: Path, *, model_dir: Path | None = None) -> dict[str, object]:
    """체크포인트를 CPU에서만 연다. weights_only=False로 다시 시도하지 않는다."""
    resolved = _confine(path, model_dir)
    blob = _read_limited(resolved)
    try:
        payload = torch.load(resolved, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, pickle.UnpicklingError, AttributeError, TypeError, ValueError) as exc:
        raise TrainError("모델 파일을 열지 못했습니다.") from exc
    if not isinstance(payload, dict):
        raise TrainError("이 연구실의 MLP 체크포인트가 아닙니다.")
    _validate_payload(payload)
    if payload.get("format") == CHECKPOINT_FORMAT_V2:
        _require_meta(resolved, payload, hashlib.sha256(blob).hexdigest())
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


def _write_checkpoint(
    path: Path,
    state: dict[str, torch.Tensor],
    *,
    hidden_dim: int,
    dropout: float,
    seed: int,
    training_dataset_fingerprint: str,
    evaluation_dataset_fingerprint: str,
    code_version: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _confine(path, path.parent)
    if path.is_symlink():
        raise TrainError("모델 파일 symlink는 쓰지 않습니다.")
    payload = _checkpoint_v2(
        state,
        hidden_dim=hidden_dim,
        dropout=dropout,
        seed=seed,
        training_dataset_fingerprint=training_dataset_fingerprint,
        evaluation_dataset_fingerprint=evaluation_dataset_fingerprint,
        code_version=code_version,
    )
    torch.save(payload, path)
    digest = hashlib.sha256(_read_limited(path)).hexdigest()
    meta = _meta(payload, path.name, digest)
    meta_path = _meta_path(path)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _checkpoint_v2(
    state: dict[str, torch.Tensor],
    *,
    hidden_dim: int,
    dropout: float,
    seed: int,
    training_dataset_fingerprint: str,
    evaluation_dataset_fingerprint: str,
    code_version: str,
) -> dict[str, object]:
    return {
        "format": CHECKPOINT_FORMAT_V2,
        "embedding_id": EMBEDDING_ID,
        "embedding_dim": EMBEDDING_DIM,
        "label_schema_version": LABEL_SCHEMA,
        "labels": list(LABELS),
        "hidden_dim": hidden_dim,
        "dropout": dropout,
        "seed": seed,
        "architecture": {
            "input_dim": EMBEDDING_DIM,
            "hidden_dim": hidden_dim,
            "num_classes": len(LABELS),
            "dropout": dropout,
        },
        "training_dataset_fingerprint": training_dataset_fingerprint,
        "evaluation_dataset_fingerprint": evaluation_dataset_fingerprint,
        "metric_policy": METRIC_POLICY,
        "code_version": code_version,
        "state_dict": state,
    }


def _meta(payload: dict[str, object], file_name: str, digest: str) -> dict[str, object]:
    state = payload["state_dict"]
    if not isinstance(state, dict):
        raise TrainError("체크포인트에 가중치가 없습니다.")
    return {
        "format": payload["format"],
        "architecture": payload["architecture"],
        "embedding_id": payload["embedding_id"],
        "embedding_dim": payload["embedding_dim"],
        "label_schema_version": payload["label_schema_version"],
        "labels": payload["labels"],
        "training_dataset_fingerprint": payload["training_dataset_fingerprint"],
        "evaluation_dataset_fingerprint": payload["evaluation_dataset_fingerprint"],
        "metric_policy": payload["metric_policy"],
        "code_version": payload["code_version"],
        "seed": payload["seed"],
        "hidden_dim": payload["hidden_dim"],
        "dropout": payload["dropout"],
        "state_dict_keys": list(_STATE_KEYS),
        "state_dict_shapes": {key: list(state[key].shape) for key in _STATE_KEYS},
        "checkpoint_file": file_name,
        "checkpoint_sha256": digest,
    }


def _validate_payload(payload: dict[str, object]) -> None:
    if payload.get("format") not in {CHECKPOINT_FORMAT_V1, CHECKPOINT_FORMAT_V2}:
        raise TrainError("지원하지 않는 체크포인트 형식입니다. 다른 형식으로 해석하지 않습니다.")
    if payload.get("embedding_id") != EMBEDDING_ID or payload.get("label_schema_version") != LABEL_SCHEMA:
        raise TrainError("임베딩 또는 라벨 체계가 다릅니다.")
    if payload.get("embedding_dim") != EMBEDDING_DIM:
        raise TrainError("임베딩 차원이 다릅니다.")
    if list(payload.get("labels") or []) != list(LABELS):
        raise TrainError("라벨 순서가 이 연구실과 다릅니다.")
    hidden = payload.get("hidden_dim")
    if not isinstance(hidden, int) or isinstance(hidden, bool) or hidden < 1:
        raise TrainError("은닉층 크기가 없습니다.")
    dropout = payload.get("dropout")
    if isinstance(dropout, bool) or not isinstance(dropout, (int, float)):
        raise TrainError("dropout이 없습니다.")
    state = payload.get("state_dict")
    if not isinstance(state, dict):
        raise TrainError("체크포인트에 가중치가 없습니다.")
    _check_state(state, hidden)
    if payload.get("format") == CHECKPOINT_FORMAT_V2:
        if payload.get("metric_policy") != METRIC_POLICY:
            raise TrainError("체크포인트의 평가 정책이 현재 정책과 다릅니다.")
        architecture = payload.get("architecture")
        if not isinstance(architecture, dict):
            raise TrainError("체크포인트에 구조 정보가 없습니다.")
        if architecture.get("input_dim") != EMBEDDING_DIM or architecture.get("hidden_dim") != hidden:
            raise TrainError("체크포인트 구조가 가중치와 다릅니다.")
        if architecture.get("num_classes") != len(LABELS):
            raise TrainError("체크포인트의 클래스 수가 다릅니다.")


def _require_meta(path: Path, payload: dict[str, object], digest: str) -> None:
    meta_path = _meta_path(path)
    _confine(meta_path, path.parent)
    if not meta_path.is_file():
        raise TrainError("체크포인트 메타데이터가 없습니다. 평가했다고 보지 않습니다.")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TrainError("체크포인트 메타데이터를 읽지 못했습니다.") from exc
    if not isinstance(meta, dict):
        raise TrainError("체크포인트 메타데이터 형식이 아닙니다.")
    if meta.get("checkpoint_sha256") != digest or meta.get("checkpoint_file") != path.name:
        raise TrainError("체크포인트 체크섬이 메타데이터와 다릅니다.")
    for key in (
        "format",
        "embedding_id",
        "embedding_dim",
        "label_schema_version",
        "labels",
        "metric_policy",
        "hidden_dim",
        "architecture",
        "training_dataset_fingerprint",
        "evaluation_dataset_fingerprint",
        "code_version",
    ):
        if meta.get(key) != payload.get(key):
            raise TrainError("체크포인트 메타데이터가 가중치 파일과 다릅니다.")
    shapes = meta.get("state_dict_shapes")
    state = payload["state_dict"]
    if not isinstance(shapes, dict) or not isinstance(state, dict):
        raise TrainError("체크포인트 메타데이터에 가중치 모양이 없습니다.")
    for key in _STATE_KEYS:
        if list(state[key].shape) != shapes.get(key):
            raise TrainError("체크포인트 메타데이터의 가중치 모양이 다릅니다.")


def _check_state(state: dict[object, object], hidden_dim: int) -> None:
    if set(state) != set(_STATE_KEYS):
        raise TrainError("체크포인트 가중치 키가 이 연구실의 MLP와 다릅니다.")
    expected = {
        "hidden.weight": (hidden_dim, EMBEDDING_DIM),
        "hidden.bias": (hidden_dim,),
        "output.weight": (len(LABELS), hidden_dim),
        "output.bias": (len(LABELS),),
    }
    for key, shape in expected.items():
        value = state[key]
        if not torch.is_tensor(value) or tuple(value.shape) != shape:
            raise TrainError("체크포인트 가중치 모양이 이 연구실의 MLP와 다릅니다.")
        if value.dtype.is_floating_point and not bool(torch.isfinite(value).all()):
            raise TrainError("가중치에 NaN 또는 Infinity가 있습니다. 이 파일을 쓰지 않습니다.")


def _model_from_payload(payload: dict[str, object]) -> MlpClassifier:
    hidden = int(payload["hidden_dim"])
    dropout = float(payload["dropout"])
    state = payload["state_dict"]
    if not isinstance(state, dict):
        raise TrainError("체크포인트에 가중치가 없습니다.")
    model = MlpClassifier(EMBEDDING_DIM, hidden, len(LABELS), dropout)
    model.load_state_dict(state)
    model.eval()
    return model


def _meta_path(path: Path) -> Path:
    return path.with_suffix(".meta.json")


def _discard(path: Path) -> None:
    meta = _meta_path(path)
    if path.is_file() and not path.is_symlink():
        path.unlink()
    if meta.is_file() and not meta.is_symlink():
        meta.unlink()


def _confine(path: Path, model_dir: Path | None) -> Path:
    if path.is_symlink():
        raise TrainError("모델 파일 symlink는 열지 않습니다.")
    root = (model_dir if model_dir is not None else path.parent).resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise TrainError("모델 경로는 모델 디렉터리 안이어야 합니다.")
    return resolved


def _read_limited(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise TrainError("모델 파일이 없습니다.")
    size = path.stat().st_size
    if size <= 0 or size > MAX_CHECKPOINT_BYTES:
        raise TrainError("모델 파일 크기가 허용 범위를 벗어났습니다.")
    return path.read_bytes()


def _predict(model: MlpClassifier, features: torch.Tensor, device: torch.device) -> list[int]:
    model.eval()
    with torch.no_grad():
        logits = model(features.to(device))
    if tuple(logits.shape) != (features.shape[0], len(LABELS)):
        raise TrainError("추론 결과의 모양이 라벨 수와 다릅니다.")
    if not bool(torch.isfinite(logits).all()):
        raise TrainError("추론 결과가 유한하지 않습니다.")
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
