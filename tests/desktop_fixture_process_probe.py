"""Explicit automated synthetic UI probe, executed only in an assigned owner Job."""
import argparse
import hashlib
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT))
from eventguard.desktop_fixture_run import run_fixture
from eventguard.events.store import EventStore
from eventguard.runtime import atomic_json
from scripts.desktop_ux_acceptance import scope_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--job', required=True)
    parser.add_argument('--phase', choices=('save', 'read'), required=True)
    parser.add_argument('--reopen-from')
    args = parser.parse_args()
    root = scope_path(args.name)
    source = scope_path(args.reopen_from) if args.reopen_from else None
    def ready(app, controller, output):
        phase, deadline = 0, time.monotonic()+6
        def tick():
            nonlocal phase
            try:
                if time.monotonic() > deadline:
                    raise TimeoutError('synthetic probe deadline')
                event_id = 'synthetic-ux-listener'
                detail = app._detail_document or {}
                if phase == 0 and app.events.exists(event_id):
                    app.events.selection_set(event_id)
                    app.select_event()
                    phase = 1
                elif phase == 1 and detail.get('event', {}).get('event_id') == event_id and not app._busy:
                    if args.phase == 'read':
                        phase = 3
                    elif app.handling_buttons['handled'].instate(['!disabled']):
                        app.handling_buttons['handled'].invoke()
                        phase = 2
                elif phase == 2 and detail.get('status') == 'handled' and app.investigate_button.instate(['!disabled']):
                    app.investigate_button.invoke()
                    phase = 3
                elif phase == 3 and detail.get('investigation') and not app._busy:
                    case = detail['investigation']['case']
                    text = app.detail.get('1.0', 'end')
                    assert detail['status'] == 'handled' and '人工處置狀態：已處理' in text
                    assert case['case_id'] in text and app.events.set(event_id, 'handling') == '已處理'
                    stats = controller.store.stats()
                    assert (stats['pending'], stats['receipt_count']) == (4, 0)
                    atomic_json(output/'probe-result.json', {'passed': True, 'automated_fixture': True,
                        'case_id': case['case_id'], 'database_sha256': hashlib.sha256(controller.store.path.read_bytes()).hexdigest(),
                        'pending': 4, 'receipts': 0, 'participant_results': None})
                    app.pause_and_exit()
                    return
                app._after(20, tick)
            except Exception as error:
                atomic_json(output/'probe-result.json', {'passed': False, 'reason': type(error).__name__, 'automated_fixture': True})
                app.pause_and_exit()
        app._after(20, tick)
    with patch('eventguard.processes.spawn', side_effect=AssertionError('no child/model')), patch(
        'eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no inventory')), patch.object(
        EventStore, 'acknowledge', side_effect=AssertionError('no ACK')):
        result = run_fixture(root, 10, args.job, reopen_root=source, on_ready=ready)
    return 0 if result['state'] == 'closed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
