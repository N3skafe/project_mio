"""python -m maidops_tui"""

from __future__ import annotations

import sys

from maidops_tui.app import MaidOpsApp
from maidops_tui.config import load_config
from maidops_tui.domain.errors import ConfigError


def main() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"오류: {exc.message}", file=sys.stderr)
        if exc.example:
            print(f"예: {exc.example}", file=sys.stderr)
        raise SystemExit(2) from exc
    MaidOpsApp(config=config).run()


if __name__ == "__main__":
    main()
