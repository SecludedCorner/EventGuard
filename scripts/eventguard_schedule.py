"""Scheduler candidate only: install/uninstall are dry-run until separately approved."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true", help="Refused in this phase; real task changes require separate approval.")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    task = "EventGuard-Monitor"
    command = subprocess.list2cmdline([sys.executable, "-B", str(root / "scripts/eventguard.py"), "monitor"])
    candidate = ["schtasks.exe", "/Create", "/TN", task, "/SC", "ONLOGON", "/RL", "LIMITED", "/IT", "/TR", command] if args.action == "install" else ["schtasks.exe", "/Delete", "/TN", task, "/F"]
    print(json.dumps({"status": "approval_required" if args.execute else "dry_run", "action": args.action,
                      "executed": False, "requires_approval": True, "candidate_argv": candidate,
                      "limitations": ["Task identity/ownership must be verified before any real change", "Logon only; no service or uptime guarantee"]}, ensure_ascii=True))
    return 2 if args.execute else 0


if __name__ == "__main__":
    raise SystemExit(main())
