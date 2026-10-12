"""학습기 테스트. 점수는 실제 혼동행렬에서만 만든다."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch

from maidops_trainer.device import TrainError, resolve_device
from maidops_trainer.embedding import HashingCharNgramEmbedder
from maidops_trainer.metrics import from_confusion
from maidops_trainer.rules import classify_failure
from maidops_trainer.train import TrainingExample, load_checkpoint, predict_label, train_classifier


def test_hashing_embedding_is_stable_and_has_no_parameters() -> None:
    embedder = HashingCharNgramEmbedder()
    first = embedder.embed("Connection to localhost:5432 refused")
    second = embedder.embed("Connection to localhost:5432 refused")
    assert torch.equal(first, second)
    assert first.shape == (256,)
    assert abs(float(torch.linalg.vector_norm(first)) - 1.0) < 1e-5


def test_macro_f1_matches_the_confusion_matrix() -> None:
    report = from_confusion(
        [
            [2, 0, 0, 0, 0],
            [0, 1, 1, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 1, 0],
            [1, 0, 0, 0, 1],
        ]
    )
    assert report.per_class[2].f1 is None
    assert report.per_class[2].support == 0
    assert report.macro_f1 == pytest.approx(47 / 60)


def test_rules_match_the_shared_keyword_list() -> None:
    assert classify_failure("permission denied for user").label == "AUTH_PERMISSION"
    assert classify_failure("status 403 from the api").matched_keyword == "403"
    assert classify_failure("org.postgresql.util.PSQLException").label == "DB_CONNECTION"
    assert classify_failure("required field email is missing").label == "INPUT_VALIDATION"
    assert classify_failure("Temporary failure in name resolution").label == "EXTERNAL_NETWORK"
    assert classify_failure("code 14013 boom").label == "OTHER"
    assert classify_failure("boom").matched_keyword is None


def test_cpu_training_beats_the_rule_baseline_on_a_fixed_split(tmp_path: Path) -> None:
    destination = tmp_path / "mv-00000001.pt"
    result = train_classifier(_separable_examples(), destination, device_request="cpu", seed=42)
    assert destination.is_file()
    assert result.device == "cpu"
    assert result.epochs_ran >= 1
    assert 0.0 <= result.macro_f1 <= 1.0
    assert 0.0 <= result.baseline_macro_f1 <= 1.0
    assert result.macro_f1 > result.baseline_macro_f1
    assert sum(sum(row) for row in result.confusion) == 4
    checkpoint = load_checkpoint(destination)
    assert checkpoint["format"] == "maidops-mlp-v1"
    assert "softmax" not in str(result.per_class)
    label = predict_label(destination, ("dbmarker " * 30) + "jdbc postgresql", result.checksum_sha256)
    assert label == "DB_CONNECTION"
    assert "0." not in label


def test_mixed_group_does_not_write_a_score(tmp_path: Path) -> None:
    examples = _separable_examples()
    leaked = examples[0]
    examples.append(
        TrainingExample(
            example_id="leak-copy",
            text=leaked.text,
            label=leaked.label,
            split="TEST",
            group_key=leaked.group_key,
        )
    )
    destination = tmp_path / "mv-00000002.pt"
    with pytest.raises(TrainError, match="그룹"):
        train_classifier(examples, destination, device_request="cpu")
    assert destination.exists() is False


def test_cuda_request_is_not_silently_rewritten() -> None:
    if torch.cuda.is_available():
        assert resolve_device("cuda").type == "cuda"
        assert resolve_device("auto").type == "cuda"
    else:
        with pytest.raises(TrainError, match="CUDA"):
            resolve_device("cuda")
        assert resolve_device("auto").type == "cpu"
        assert resolve_device("cpu").type == "cpu"


def test_arbitrary_file_is_not_a_model(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("not a model", encoding="utf-8")
    with pytest.raises(TrainError):
        load_checkpoint(path)


def _separable_examples() -> list[TrainingExample]:
    """토큰은 정답, 키워드는 절반만 맞는다. 규칙은 두 클래스를 모두 예측한다."""
    rows: list[TrainingExample] = []
    plan = (("TRAIN", 12), ("VAL", 4), ("TEST", 4))
    keywords = (
        "permission denied for role",
        "postgresql database",
        "jdbc postgresql",
        "access denied",
    )
    for split, count in plan:
        for index in range(count):
            label = "DB_CONNECTION" if index % 2 == 0 else "AUTH_PERMISSION"
            token = "dbmarker" if label == "DB_CONNECTION" else "authmarker"
            text = (token + " ") * 30 + keywords[index % 4]
            rows.append(
                TrainingExample(
                    example_id=f"{split}-{index}",
                    text=text,
                    label=label,
                    split=split,
                    group_key=f"{split}-{token}-{index}",
                )
            )
    return rows
