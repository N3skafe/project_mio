import subprocess
import sys
import time


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "child" and sys.argv[2] == "grandchild":
        time.sleep(60)
        return 0
    if len(sys.argv) >= 2 and sys.argv[1] == "child":
        subprocess.Popen([sys.executable, __file__, "child", "grandchild"])
        time.sleep(60)
        return 0
    print("tree-start", flush=True)
    subprocess.Popen([sys.executable, __file__, "child"])
    time.sleep(60)
    print("tree-done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
