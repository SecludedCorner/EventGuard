"""Internal owned CLI capture worker; use acceptance_codex.py for user commands."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventguard.acceptance_process import main

if __name__ == "__main__":
    raise SystemExit(main())
