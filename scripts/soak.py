"""Finite synthetic-only reliability exercise; no collectors, CLI or model."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from eventguard.soak import main

if __name__ == "__main__":
    raise SystemExit(main())
