"""Compatibility entry: new single runs use the canonical QueueInbox harness."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main():
    values = sys.argv[1:]
    if values[:1] == ["run"]:
        from eventguard.delivery_validation import main as validate
        return validate(["single", *("--root" if v == "--run-dir" else v for v in values[1:])])
    if values[:1] in (["status"], ["stop"]):
        from eventguard.codex_acceptance import main as legacy
        return legacy(values)  # Existing old evidence only; no model is started.
    print('Legacy execution/retry is retired. Use validate_delivery.py; --execute needs current approval.', file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
