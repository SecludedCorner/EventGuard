"""Bounded event-driven Codex inbox dispatcher; does not install a service."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventguard.agent_dispatch import main

if __name__ == "__main__":
    raise SystemExit(main())
