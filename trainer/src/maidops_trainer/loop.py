"""대기 중인 학습만 집어 실행한다. 끝나면 기본 모델로 바꾸지 않는다."""

from __future__ import annotations

import os
import re
import subprocess
import time
import uuid
from pathlib import Path

from maidops_trainer.client import TrainerApi
from maidops_trainer.device import TrainError
from maidops_trainer.train import TrainingExample, predict_label, train_classifier


def run_loop(
    *,
    base_url: str,
    model_dir: Path,
    trainer_id: str | None = None,
    device: str = "auto",
    once: bool = False,
    idle_seconds: float = 2.0,
) -> None:
    identity = trainer_id or f"trainer-{uuid.uuid4().hex[:8]}"
    api = TrainerApi(base_url, identity)
    alive = Path(os.environ["MAIDOPS_TRAINER_ALIVE_FILE"]) if os.environ.get("MAIDOPS_TRAINER_ALIVE_FILE") else None
    try:
        while True:
            _touch(alive)
            claimed = api.claim()
            if claimed is not None:
                _train_claimed(api, claimed, model_dir, device)
                if once:
                    return
                continue
            draft = api.claim_inference()
            if draft is not None:
                _infer_claimed(api, draft, model_dir)
                if once:
                    return
                continue
            if once:
                return
            time.sleep(idle_seconds)
    finally:
        api.close()


def _train_claimed(api: TrainerApi, claimed: dict[str, object], model_dir: Path, device: str) -> None:
    run_id = str(claimed["training_run_id"])
    model_id = str(claimed["reserved_model_id"])
    model_path = model_dir / f"{model_id}.pt"
    try:
        rows = [
            TrainingExample(
                example_id=str(item["error_case_id"]),
                text=str(item["raw_text"]),
                label=str(item["label"]),
                split=str(item["split"]),
                group_key=str(item["group_key"]),
            )
            for item in api.examples(run_id)
        ]

        def heartbeat() -> None:
            body = api.heartbeat(run_id)
            if body.get("cancel_requested") is True:
                raise TrainError("사용자가 학습 취소를 요청했습니다. 모델을 저장하지 않습니다.")

        result = train_classifier(
            rows,
            model_path,
            seed=int(claimed["seed"]),
            device_request=device,
            heartbeat=heartbeat,
        )
        api.complete(
            run_id,
            {
                "embedding_id": str(claimed["embedding_id"]),
                "label_schema_version": str(claimed["label_schema_version"]),
                "code_version": code_version(),
                "device": result.device,
                "seed": int(claimed["seed"]),
                "config": result.config,
                "macro_f1": result.macro_f1,
                "per_class": result.per_class,
                "confusion_matrix": result.confusion,
                "baseline_macro_f1": result.baseline_macro_f1,
                "baseline_per_class": result.baseline_per_class,
                "baseline_confusion_matrix": result.baseline_confusion,
            },
        )
    except (TrainError, OSError, ValueError, KeyError) as exc:
        if model_path.exists():
            model_path.unlink()
        api.fail(run_id, str(exc) or "학습에 실패했습니다. 평가 점수를 저장하지 않았습니다.")


def _infer_claimed(api: TrainerApi, claimed: dict[str, object], model_dir: Path) -> None:
    inference_id = str(claimed["inference_id"])
    model_path = model_dir / str(claimed["model_file"])
    try:
        label = predict_label(model_path, str(claimed["raw_text"]), str(claimed["checksum_sha256"]))
        api.complete_inference(inference_id, label)
    except (TrainError, OSError, ValueError, KeyError) as exc:
        api.fail_inference(inference_id, str(exc) or "모델 초안을 만들지 못했습니다.")


def code_version() -> str:
    root = Path(os.environ.get("MAIDOPS_CODE_ROOT", Path.cwd()))
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    if completed.returncode != 0:
        return "unknown"
    value = completed.stdout.strip().lower()
    if re.fullmatch(r"[0-9a-f]{7,40}", value):
        return value
    return "unknown"


def _touch(path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
