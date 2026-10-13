import sys

print("boom", file=sys.stderr, flush=True)
sys.exit(2)
