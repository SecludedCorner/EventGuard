"""Copy a known complete local bundle and run only bounded no-model probes."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from eventguard.codex_runtime import snapshot
from eventguard.codex_preflight import run


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Installed codex.exe; read only')
    parser.add_argument('--root', type=Path, required=True, help='New private bundle directory')
    args = parser.parse_args()
    try:
        snapshot(args.source, args.root)
        proof = run(args.root/'codex.exe')
        print(json.dumps(dict(state='no_model_preflight_passed', version=proof['version'], model_calls=0)))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        print(json.dumps(dict(state='no_model_preflight_failed', raw_error_omitted=True, model_calls=0)))
        raise SystemExit(2)
