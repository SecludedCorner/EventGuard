from pathlib import Path
from .cli import main
raise SystemExit(main(root=Path(__file__).resolve().parents[2]))
