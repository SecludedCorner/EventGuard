"""Use installed Python directly. No installation, sys.path only inside this project."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"src"))
from eventguard.cli import main
raise SystemExit(main(root=ROOT))
