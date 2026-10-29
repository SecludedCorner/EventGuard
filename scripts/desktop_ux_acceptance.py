"""Explicit finite synthetic desktop acceptance, never a native scan/model task."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from eventguard.processes import spawn, finish
from eventguard.runtime import Runtime, atomic_json, read_json


def launch(name, seconds=900, *, cancel_after=None):
    if not isinstance(name, str) or re.fullmatch(r'desktop-ux-[A-Za-z0-9_-]{1,64}', name) is None:
        raise ValueError('desktop_fixture_name_invalid')
    if type(seconds) is not int or not 1 <= seconds <= 900:
        raise ValueError('desktop_fixture_duration_invalid')
    if cancel_after is not None and (type(cancel_after) not in (int, float) or not 0 < cancel_after <= seconds):
        raise ValueError('desktop_fixture_cancel_invalid')
    if os.name != 'nt':
        return {'status': 'unsupported', 'reason': 'windows_owned_job_required', 'synthetic': True}
    runtime = Runtime(ROOT)
    runtime.path('reports').mkdir(exist_ok=True)
    root = runtime.path(Path('reports')/name)
    root.mkdir(exist_ok=False)
    from eventguard.desktop_ux_tasks import prepare_tasks
    prepare_tasks(root)
    job_name = 'Local\\EventGuard-'+uuid.uuid4().hex
    child = spawn([sys.executable, '-B', str(Path(__file__).resolve()), '--worker', str(root),
                   '--job', job_name, '--seconds', str(seconds)], job_name=job_name, stdin=subprocess.PIPE)
    try:
        atomic_json(root/'guardian-start.json', {'synthetic': True, 'pid': child.pid,
            'created_at': child.created_at, 'job_name': job_name, 'model_calls': 0})
        try:
            child.wait(timeout=cancel_after if cancel_after is not None else seconds+10)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            pass
    finally:
        receipt = finish(child, 'cancelled' if child.poll() is None else 'descendants_remaining', grace=5)
        atomic_json(root/'guardian-exit.json', receipt)
    worker = read_json(root/'worker-exit.json') if (root/'worker-exit.json').is_file() else {}
    ready = read_json(root/'worker-ready.json') if (root/'worker-ready.json').is_file() else {}
    passed = (receipt.get('managed') is True and receipt.get('child_exited') is True and receipt.get('exit_code') == 0
        and receipt.get('remaining_owned_processes') == 0 and receipt.get('forcibly_terminated') is False
        and worker.get('state') == 'closed' and worker.get('gui_worker_exited') is True
        and ready.get('membership_verified') is True)
    result = {'status': 'synthetic_session_closed' if passed else 'unconfirmed', 'synthetic': True,
              'root': 'reports/'+name, 'guardian': receipt, 'worker': worker,
              'participant_results': None, 'machine_scan_executed': False, 'model_calls': 0}
    atomic_json(root/'session-result.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', help='新reports/desktop-ux-<名稱>，既有目錄拒絕覆寫')
    parser.add_argument('--seconds', type=int, default=900, help='1–900秒，逾時合作關閉')
    parser.add_argument('--worker', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--job', help=argparse.SUPPRESS)
    parser.add_argument('--record-task', choices=('U1', 'U2', 'U3', 'U4', 'U5', 'U6'))
    parser.add_argument('--steps', type=int)
    parser.add_argument('--elapsed-seconds', type=float)
    parser.add_argument('--errors', type=int)
    parser.add_argument('--outcome', choices=('completed', 'failed', 'unresolved'))
    args = parser.parse_args(argv)
    try:
        if args.worker is not None:
            root = args.worker.absolute()
            if root.parent != ROOT/'reports' or re.fullmatch(r'desktop-ux-[A-Za-z0-9_-]{1,64}', root.name) is None:
                raise ValueError('desktop_fixture_worker_scope_invalid')
            root = Runtime(ROOT).path(Path('reports')/root.name)
            from eventguard.desktop_fixture_run import run_fixture
            result = run_fixture(root, args.seconds, args.job)
            return 0 if result['state'] == 'closed' and result['gui_worker_exited'] else 2
        if args.record_task:
            if not isinstance(args.name, str) or re.fullmatch(r'desktop-ux-[A-Za-z0-9_-]{1,64}', args.name) is None:
                raise ValueError('desktop_fixture_name_invalid')
            from eventguard.desktop_ux_tasks import record_task
            result = record_task(Runtime(ROOT).path(Path('reports')/args.name), args.record_task,
                                 args.steps, args.elapsed_seconds, args.errors, args.outcome)
            print(json.dumps(result, ensure_ascii=True))
            return 0
        result = launch(args.name, args.seconds)
        print(json.dumps(result, ensure_ascii=True))
        return 0 if result['status'] == 'synthetic_session_closed' else 2
    except Exception as error:
        print(json.dumps({'status': 'blocked', 'reason': type(error).__name__, 'raw_error_omitted': True}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
