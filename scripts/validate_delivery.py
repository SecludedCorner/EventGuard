"""Canonical finite QueueInbox acceptance; no model without explicit --execute."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from eventguard.delivery_validation import main

if __name__ == "__main__":
    raise SystemExit(main())
