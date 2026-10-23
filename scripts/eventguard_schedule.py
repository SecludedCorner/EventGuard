"""Review a current-user logon task; mutations require an approved plan digest."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eventguard.schedule import main


if __name__ == "__main__":
    raise SystemExit(main(root=Path(__file__).resolve().parents[1]))
