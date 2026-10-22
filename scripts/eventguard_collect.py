"""Internal native collector worker. Typed section only; no model or command input."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventguard.collectors.contract import SECTION_IDS, evidence
from eventguard.collectors.native import NativeBackend


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=SECTION_IDS, required=True)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    try:
        result = NativeBackend(timeout=args.timeout).collect(args.section)
    except Exception:
        result = {"status": "error", "rows": [], "errors": [evidence("provider", "native_worker_failed", status="error")]}
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
