"""Automated real Tk lost-success/recovery probe, never participant results."""
from contextlib import ExitStack
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
    for flag in ('name', 'job', 'phase', 'reopen-from'):
        parser.add_argument('--'+flag, required=flag != 'reopen-from')
    args = parser.parse_args()
    if args.phase not in ('loss', 'recover'):
        raise ValueError('invalid_probe_phase')
    source = scope_path(args.reopen_from) if args.reopen_from else None
    with ExitStack() as stack:
        def ready(app, controller, output):
            phase, deadline, calls, expected, before = 0, time.monotonic()+7, [], None, None
            event_id = 'synthetic-ux-listener'
            original = controller.set_status_durable
            def save(*values):
                calls.append(values[2])
                result = original(*values)
                if args.phase == 'loss':
                    raise OSError('synthetic lost success reply')
                return result
            stack.enter_context(patch.object(controller, 'set_status_durable', side_effect=save))
            def tick():
                nonlocal phase, expected, before
                try:
                    if time.monotonic() > deadline:
                        raise TimeoutError('probe deadline')
                    detail = app._detail_document or {}
                    if phase == 0 and app.events.exists(event_id):
                        app.events.selection_set(event_id)
                        app.select_event()
                        phase = 1
                    elif phase == 1 and detail.get('event', {}).get('event_id') == event_id and not app._busy:
                        if args.phase == 'recover':
                            expected = detail['pending_handling_requests']['requests'][0]['operation_id']
                            assert app._pending_status[(event_id, 'handled')] == expected and not calls
                            assert detail['status'] == 'read' and '未確認要求：已處理' in app.handling_status.get()
                            before = hashlib.sha256(controller.store.path.read_bytes()).hexdigest()
                        app.handling_buttons['handled'].invoke()
                        phase = 2
                    elif phase == 2 and not app._busy and ((args.phase == 'loss' and '結果未確認' in app.message.get())
                                                         or (args.phase == 'recover' and '人工狀態已核對' in app.message.get())):
                        current = controller.catalog.detail(event_id)
                        if args.phase == 'loss':
                            expected = current['pending_handling_requests']['requests'][0]['operation_id']
                            assert calls == [expected] and current['status'] == 'handled'
                            controller.catalog.set_status(event_id, 'read', source='cli', operation_id='later-process-decision')
                            current = controller.catalog.detail(event_id)
                        else:
                            assert calls == [expected] and current['pending_handling_requests']['requests'] == []
                            assert app._pending_status == {} and current['status'] == 'read'
                        stats = controller.store.stats()
                        assert (stats['pending'], stats['receipt_count']) == (4, 0)
                        assert [r['status'] for r in current['handling_history']['entries']] == ['handled', 'read']
                        atomic_json(output/'request-probe.json', {'passed': True, 'automated_fixture': True,
                            'phase': args.phase, 'operation_id': expected, 'status': current['status'],
                            'pre_replay_sha256': before, 'final_db_sha256': hashlib.sha256(controller.store.path.read_bytes()).hexdigest(),
                            'calls': calls, 'pending_requests': len(current['pending_handling_requests']['requests']),
                            'pending': 4, 'receipts': 0, 'participant_results': None})
                        app.pause_and_exit()
                        return
                    app._after(20, tick)
                except Exception as error:
                    atomic_json(output/'request-probe.json', {'passed': False, 'reason': type(error).__name__, 'automated_fixture': True})
                    app.pause_and_exit()
            app._after(20, tick)
        stack.enter_context(patch('eventguard.processes.spawn', side_effect=AssertionError('no child/model')))
        stack.enter_context(patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no scan')))
        stack.enter_context(patch.object(EventStore, 'acknowledge', side_effect=AssertionError('no ACK')))
        result = run_fixture(scope_path(args.name), 10, args.job, reopen_root=source, on_ready=ready)
    return 0 if result['state'] == 'closed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
