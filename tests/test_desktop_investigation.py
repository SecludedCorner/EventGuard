"""Explicit desktop metadata investigation with isolated synthetic events."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eventguard import activity
from eventguard.desktop import DesktopController
from eventguard.events.catalog import EventCatalog
from eventguard.events.store import CapacityError, EventStore
from test_event_investigation import fixture_events


class DesktopInvestigationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root/'data/live')
        for event in fixture_events()[:2]:
            self.store.enqueue(event)
        self.catalog = EventCatalog(self.root, 'live')
        self.controller = DesktopController(self.root)
        self.enterContext(patch('eventguard.processes.spawn', side_effect=AssertionError('no child or model')))
        self.enterContext(patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no scan')))
        self.enterContext(patch.object(EventStore, 'acknowledge', side_effect=AssertionError('no ACK')))

    def test_explicit_save_and_reopen_preserve_pending_and_record_bounded_activity(self):
        self.assertIsNone(self.catalog.detail('evt-anchor')['investigation'])
        result = self.controller.investigate('evt-anchor')
        self.assertEqual(result['state'], 'investigation_saved')
        self.assertEqual(result['event_id'], 'evt-anchor')
        self.assertEqual(result['model_calls'], 0)
        self.assertFalse(result['system_query_executed'])
        self.assertFalse(result['ack_performed'])
        saved = self.controller.inspect('evt-anchor')
        self.assertEqual(saved['investigation']['case']['case_id'], result['investigation']['case']['case_id'])
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))
        entries = activity.snapshot(self.root, 'live')['entries']
        entry = next(item for item in entries if item['operation'] == 'gui_investigate')
        self.assertEqual(entry['state'], 'completed')
        self.assertEqual(entry['result_code'], 'investigation_saved')
        self.assertEqual(len(entry['target_ref']), 16)
        self.assertNotIn(b'evt-anchor', (self.root/'data/activity.sqlite3').read_bytes())

    def test_capacity_failure_preserves_old_case_and_pending_without_false_completion(self):
        self.controller.investigate('evt-anchor')
        before = self.store.path.read_bytes()
        with patch.object(EventStore, 'save_investigation', side_effect=CapacityError('investigation_capacity_pending_and_ack_space_preserved')):
            with self.assertRaises(CapacityError):
                self.controller.investigate('evt-anchor')
        self.assertEqual(self.store.path.read_bytes(), before)
        entries = activity.snapshot(self.root, 'live')['entries']
        self.assertTrue(any(item['operation'] == 'gui_investigate' and item['state'] == 'failed' for item in entries))
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (2, 0))

    def test_journal_failure_blocks_save_and_missing_event_is_not_created(self):
        before = self.store.path.read_bytes()
        with patch('eventguard.activity.begin', side_effect=activity.ActivityError('activity_storage_unavailable')):
            blocked = self.controller.investigate('evt-anchor')
        self.assertFalse(blocked['operation_started'])
        self.assertEqual(self.store.path.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'event_not_found'):
            self.controller.investigate('missing-event')
        self.assertEqual(self.store.path.read_bytes(), before)
