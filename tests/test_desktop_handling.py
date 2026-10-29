"""Human desktop decisions on real synthetic SQLite; delivery stays pending."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard import activity
from eventguard.desktop import DesktopController
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import CapacityError, EventStore
from eventguard.synthetic import make_synthetic


class DesktopHandlingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root/'data/live')
        self.event = make_synthetic('listener')
        self.store.enqueue(self.event)
        self.event_id = self.event['event_id']
        self.catalog = EventCatalog(self.root, 'live')
        self.controller = DesktopController(self.root)
        self.enterContext(patch.object(EventStore, 'acknowledge', side_effect=AssertionError('no ACK')))
        self.enterContext(patch('eventguard.processes.spawn', side_effect=AssertionError('no child/model')))
        self.enterContext(patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no scan')))

    def test_four_human_states_are_separate_from_ack_and_keep_history(self):
        for status in ('read', 'handled', 'ignored', 'new'):
            result = self.controller.set_status(self.event_id, status, 'op-'+status)
            self.assertEqual((result['state'], result['status']), ('event_status_updated', status))
            self.assertFalse(result['ack_performed'])
            self.assertFalse(result['system_query_executed'])
            self.assertEqual(result['model_calls'], 0)
            self.assertEqual(self.catalog.detail(self.event_id)['event']['delivery_status'], 'pending')
        entries = self.catalog.detail(self.event_id)['handling_history']['entries']
        self.assertEqual([x['status'] for x in entries], ['read', 'handled', 'ignored', 'new'])
        self.assertTrue(all(x['source'] == 'gui' for x in entries))
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))

    def test_replayed_operation_does_not_revert_a_later_decision(self):
        self.controller.set_status(self.event_id, 'read', 'op-first')
        self.controller.set_status(self.event_id, 'handled', 'op-later')
        result = self.controller.set_status(self.event_id, 'read', 'op-first')
        self.assertTrue(result['history_replayed'])
        self.assertEqual(result['status'], 'handled')
        self.assertEqual(len(self.catalog.detail(self.event_id)['handling_history']['entries']), 2)

    def test_capacity_and_activity_failure_preserve_status_and_pending(self):
        self.controller.set_status(self.event_id, 'read', 'op-first')
        before = self.store.path.read_bytes()
        with patch.object(EventStore, 'set_disposition', side_effect=CapacityError('synthetic capacity')):
            with self.assertRaises(CapacityError):
                self.controller.set_status(self.event_id, 'handled', 'op-capacity')
        with patch('eventguard.activity.begin', side_effect=activity.ActivityError('activity_storage_unavailable')):
            result = self.controller.set_status(self.event_id, 'handled', 'op-blocked')
            self.assertFalse(result['operation_started'])
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(self.catalog.detail(self.event_id)['status'], 'read')
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))

    def test_invalid_status_or_missing_operation_key_never_changes_delivery(self):
        before = self.store.path.read_bytes()
        for status, operation in [('ack', 'op-invalid'), ('handled', None), ('handled', '')]:
            with self.assertRaises(ValueError):
                self.controller.set_status(self.event_id, status, operation)
        self.assertEqual(self.store.path.read_bytes(), before)
