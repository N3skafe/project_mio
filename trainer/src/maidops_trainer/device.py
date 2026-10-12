"""CPU를 기본으로 하고, CUDA는 사용할 수 있을 때만 선택한다."""

from __future__ import annotations

import torch


class TrainError(Exception):
    """학습을 점수 없이 중단할 때 쓴다."""


def resolve_device(requested: str) -> torch.device:
    choice = requested.strip().lower()
    if choice == "cpu":
        return torch.device("cpu")
    if choice == "cuda":
        if not torch.cuda.is_available():
            raise TrainError("CUDA를 요청했지만 사용할 수 없습니다. CPU로 바꾸지 않았습니다.")
        return torch.device("cuda")
    if choice == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
    raise TrainError("장치는 cpu, cuda, auto 중 하나여야 합니다.")
