"""python -m maidops_worker"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from maidops_worker.loop import run_loop


def main() -> None:
    base_url = os.environ.get("MAIDOPS_BACKEND_URL", "http://127.0.0.1:8080")
    root = os.environ.get("MAIDOPS_WORKSPACE_ROOT", "")
    if not root:
        print("오류: MAIDOPS_WORKSPACE_ROOT가 필요합니다.", file=sys.stderr)
        raise SystemExit(2)
    run_loop(base_url=base_url, workspace_root=Path(root), worker_id=os.environ.get("MAIDOPS_WORKER_ID"))


if __name__ == "__main__":
    main()
