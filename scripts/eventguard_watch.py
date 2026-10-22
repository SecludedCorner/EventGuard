"""Explicit bounded foreground live monitoring and event-driven Codex delivery."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventguard.watch import main

if __name__ == "__main__":
    raise SystemExit(main())
