"""학습기 진입점. 환경 변수만 읽고 사용자 문장을 실행하지 않는다."""

from __future__ import annotations

import os
from pathlib import Path

from maidops_trainer.loop import run_loop


def main() -> None:
    base_url = os.environ.get("MAIDOPS_BACKEND_URL", "http://127.0.0.1:8080")
    model_dir = Path(os.environ.get("MAIDOPS_MODEL_DIR", "data/models"))
    device = os.environ.get("MAIDOPS_TRAIN_DEVICE", "auto")
    run_loop(base_url=base_url, model_dir=model_dir, device=device)


if __name__ == "__main__":
    main()
