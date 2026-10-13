"""저장한 체크포인트를 다시 읽어 거절 조건을 확인한다. 기존 사용자 모델 파일은 쓰지 않는다."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch

from maidops_trainer.device import TrainError
from maidops_trainer.embedding import EMBEDDING_DIM, EMBEDDING_ID
from maidops_trainer.metrics import LABELS, from_confusion
from maidops_trainer.train import (
    CHECKPOINT_FORMAT_V1,
    CHECKPOINT_FORMAT_V2,
    MlpClassifier,
    TrainingExample,
    load_checkpoint,
    predict_label,
    train_classifier,
)


def test_reloaded_file_is_the_score_that_is_returned(tmp_path: Path) -> None:
    destination = tmp_path / "mv-00000011.pt"
    result = train_classifier(_rows(), destination, device_request="cpu", seed=42, training_dataset_fingerprint="train-fp")
    meta = json_meta(destination)
    assert result.checkpoint_evaluated is True
    assert result.metric_policy == "supported-class-macro-f1-v2"
    assert meta["format"] == CHECKPOINT_FORMAT_V2
    assert meta["checkpoint_sha256"] == result.checksum_sha256
    assert meta["metric_policy"] == result.metric_policy
    assert meta["evaluation_dataset_fingerprint"] == result.evaluation_fingerprint
    assert meta["training_dataset_fingerprint"] == "train-fp"
    assert meta["labels"] == list(LABELS)
    assert from_confusion(result.confusion).macro_f1 == pytest.approx(result.macro_f1)
    assert sum(sum(row) for row in result.confusion) == result.evaluation_sample_count


def test_text_truncated_metadata_shape_checksum_and_nan_are_rejected(tmp_path: Path) -> None:
    text = tmp_path / "notes.txt"
    text.write_text("not a model", encoding="utf-8")
    with pytest.raises(TrainError):
        load_checkpoint(text)

    good = tmp_path / "mv-00000012.pt"
    train_classifier(_rows(), good, device_request="cpu", seed=42)
    truncated = tmp_path / "mv-00000013.pt"
    truncated.write_bytes(good.read_bytes()[:24])
    with pytest.raises(TrainError):
        load_checkpoint(truncated)

    broken_meta = json_meta(good)
    broken_meta["embedding_dim"] = 32
    meta_path(good).write_text(__import__("json").dumps(broken_meta), encoding="utf-8")
    with pytest.raises(TrainError, match="메타데이터"):
        load_checkpoint(good)

    wrong_shape = tmp_path / "mv-00000014.pt"
    torch.save(_payload(_state(weight_shape=(64, 128))), wrong_shape)
    with pytest.raises(TrainError, match="모양"):
        load_checkpoint(wrong_shape)

    wrong_labels = tmp_path / "mv-00000015.pt"
    payload = _payload(_state())
    payload["labels"] = list(reversed(LABELS))
    torch.save(payload, wrong_labels)
    with pytest.raises(TrainError, match="라벨"):
        load_checkpoint(wrong_labels)

    nan_path = tmp_path / "mv-00000016.pt"
    torch.save(_payload(_state(nan=True)), nan_path)
    with pytest.raises(TrainError, match="NaN"):
        load_checkpoint(nan_path)

    fresh = tmp_path / "mv-00000017.pt"
    trained = train_classifier(_rows(), fresh, device_request="cpu", seed=42)
    meta = json_meta(fresh)
    assert meta["format"] == CHECKPOINT_FORMAT_V2
    assert meta["embedding_id"] == EMBEDDING_ID
    assert meta["embedding_dim"] == EMBEDDING_DIM
    assert meta["labels"] == list(LABELS)
    assert meta["checkpoint_sha256"] == trained.checksum_sha256
    with pytest.raises(TrainError, match="체크섬"):
        predict_label(fresh, "dbmarker jdbc postgresql", "0" * 64)
    assert predict_label(fresh, ("dbmarker " * 30) + "jdbc postgresql", trained.checksum_sha256) == "DB_CONNECTION"


def test_v1_file_loads_for_inference_without_an_evaluation_claim(tmp_path: Path) -> None:
    path = tmp_path / "mv-00000018.pt"
    torch.save(_payload(_state(), fmt=CHECKPOINT_FORMAT_V1), path)
    payload = load_checkpoint(path)
    assert payload["format"] == CHECKPOINT_FORMAT_V1
    assert meta_path(path).exists() is False


def test_empty_evaluation_does_not_write_a_score(tmp_path: Path) -> None:
    rows = [row for row in _rows() if row.split != "TEST"]
    destination = tmp_path / "mv-00000019.pt"
    with pytest.raises(TrainError, match="분할"):
        train_classifier(rows, destination, device_request="cpu")
    assert destination.exists() is False
    with pytest.raises(ValueError):
        from_confusion([[0, 0, 0, 0, 0] for _ in range(5)])


def test_path_outside_the_model_dir_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path / "outside.pt"
    outside.write_bytes(b"nope")
    root = tmp_path / "models"
    root.mkdir()
    with pytest.raises(TrainError, match="디렉터리"):
        load_checkpoint(outside, model_dir=root)


def _rows() -> list[TrainingExample]:
    rows: list[TrainingExample] = []
    plan = (("TRAIN", 8), ("VAL", 4), ("TEST", 4))
    for split, count in plan:
        for index in range(count):
            label = "DB_CONNECTION" if index % 2 == 0 else "AUTH_PERMISSION"
            token = "dbmarker" if label == "DB_CONNECTION" else "authmarker"
            rows.append(
                TrainingExample(
                    example_id=f"{split}-{index}",
                    text=(token + " ") * 20 + "jdbc postgresql",
                    label=label,
                    split=split,
                    group_key=f"{split}-{token}-{index}",
                )
            )
    return rows


def _state(*, weight_shape: tuple[int, int] = (64, EMBEDDING_DIM), nan: bool = False) -> dict[str, torch.Tensor]:
    model = MlpClassifier(EMBEDDING_DIM, 64, len(LABELS), 0.0)
    state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if weight_shape != (64, EMBEDDING_DIM):
        state["hidden.weight"] = torch.zeros(weight_shape)
    if nan:
        state["hidden.weight"][0, 0] = float("nan")
    return state


def _payload(state: dict[str, torch.Tensor], *, fmt: str = CHECKPOINT_FORMAT_V2) -> dict[str, object]:
    return {
        "format": fmt,
        "embedding_id": EMBEDDING_ID,
        "embedding_dim": EMBEDDING_DIM,
        "label_schema_version": "labels-1",
        "labels": list(LABELS),
        "hidden_dim": 64,
        "dropout": 0.0,
        "seed": 42,
        "metric_policy": "supported-class-macro-f1-v2",
        "architecture": {"input_dim": EMBEDDING_DIM, "hidden_dim": 64, "num_classes": 5, "dropout": 0.0},
        "training_dataset_fingerprint": "train",
        "evaluation_dataset_fingerprint": "eval",
        "code_version": "unknown",
        "state_dict": state,
    }


def meta_path(path: Path) -> Path:
    return path.with_suffix(".meta.json")


def json_meta(path: Path) -> dict[str, object]:
    return __import__("json").loads(meta_path(path).read_text(encoding="utf-8"))
