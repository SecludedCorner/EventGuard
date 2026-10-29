"""Real desktop controller/worker reads synthetic pending pages, never scans."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from eventguard.desktop import DesktopController
from eventguard.events.schema import validate_event
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.gui import ControllerWorker
from eventguard.synthetic import make_synthetic


class DesktopPendingControlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = EventStore(self.root/'data/live')
        events = [dict(make_synthetic('listener'), event_id=f'synthetic-desktop-{i:03}') for i in range(101)]
        self.store.commit_evaluation({'synthetic_fixture': True}, events)
        self.anchor = events[0]['event_id']
        with self.store._connect() as db:
            db.execute('UPDATE events SET created_at=0 WHERE event_id=?', (self.anchor,))
        self.intent = {'namespace': 'live', 'event_id': self.anchor, 'status': 'handled', 'operation_id': 'old-desktop-pending',
                       'payload_hash': event_payload_hash(validate_event(self.store.get_event(self.anchor)))}
        self.store._prepare_desktop_request(self.intent, namespace='live')
        self.controller = DesktopController(self.root)
        self.controller.api = Mock()
        self.controller.api.call.side_effect = lambda *a, **kw: {
            'event_storage': {'state': 'available', 'counts': self.store.stats()},
            'event_list': {'events': self.store.list_events(limit=100), 'total': 101, 'truncated': True}}
        self.enterContext(patch('eventguard.processes.spawn', side_effect=AssertionError('no child/model')))
        self.enterContext(patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no scan')))
        self.enterContext(patch.object(EventStore, 'acknowledge', side_effect=AssertionError('no ACK')))

    def test_controller_discovers_hidden_anchor_without_expanding_recent_snapshot(self):
        before = self.store.path.read_bytes()
        recent = self.controller.snapshot()
        self.assertEqual(len(recent['events']), 100)
        self.assertNotIn(self.anchor, {e['event_id'] for e in recent['events']})
        result = self.controller.pending_requests()
        self.assertEqual((result['state'], result['namespace'], result['total']), ('available', 'live', 1))
        self.assertEqual(result['events'][0]['event_id'], self.anchor)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (101, 0))

    def test_worker_correlates_offset_and_never_dispatches_state_or_exposes_exception_text(self):
        for offset, state in ((0, 'available'), (129, 'error')):
            worker = ControllerWorker(self.controller)
            try:
                self.assertTrue(worker.submit('pending_requests', offset))
                action, result = worker.results.get(timeout=4)
                self.assertEqual((action, result['requested_offset'], result['state']), ('pending_requests', offset, state))
                if state == 'available':
                    self.assertEqual(result['total'], 1)
                self.assertNotIn('raw_error', result)
            finally:
                worker.shutdown(wait=True)
            self.assertFalse(worker.thread.is_alive())
