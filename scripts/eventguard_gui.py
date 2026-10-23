"""Local Tk application; no model, scheduler or dependency installation."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main(argv=None):
    if sys.version_info[:2] != (3, 13):
        return 2
    from eventguard.gui import main as run_gui
    from eventguard.runtime import atomic_json
    from eventguard.processes import cleanup_owned
    result = run_gui(argv, root=ROOT)
    receipts = cleanup_owned(grace=2)
    if receipts:
        result = dict(result, final_owned_cleanup=receipts)
    try:
        atomic_json(ROOT / "data/gui-last-exit.json", result)
    except (OSError, ValueError):
        return 4
    return 0 if result.get("can_close") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
