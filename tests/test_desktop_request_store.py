"""EventStore transaction/ACK-reserve integration; no UI dispatch yet."""
from unittest.mock import patch
import unittest

from eventguard.desktop_requests import pending
from eventguard.events.store import CapacityError, EventStore
import test_desktop_requests as fixture


class DesktopRequestStoreTests(unittest.TestCase):
    setUp = fixture.DesktopRequestTests.setUp
    connect = fixture.DesktopRequestTests.connect

    def test_late_capacity_failure_rolls_back_new_schema_and_intent(self):
        before = self.store.path.read_bytes()
        with patch.object(self.store, '_used_bytes', side_effect=[0, self.store.max_bytes]):
            with self.assertRaises(CapacityError):
                self.store._prepare_desktop_request(self.value, namespace='test')
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))

    def test_restart_then_resolve_requires_original_durable_gui_operation(self):
        from contextlib import closing
        self.assertFalse(self.store._prepare_desktop_request(self.value, namespace='test')['caller_commit_required'])
        reopened = EventStore(self.store.directory)
        before = reopened.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'desktop_request_completion_unverified'):
            reopened._complete_desktop_request(self.value, namespace='test')
        self.assertEqual(reopened.path.read_bytes(), before)
        reopened.set_disposition(self.value['event_id'], 'handled', source='gui', operation_id=self.value['operation_id'])
        reopened.set_disposition(self.value['event_id'], 'read', source='cli', operation_id='later-human')
        with patch.object(reopened, '_used_bytes', return_value=reopened.max_bytes):
            self.assertTrue(reopened._prepare_desktop_request(self.value, namespace='test')['replayed'])
        self.assertTrue(reopened._complete_desktop_request(self.value, namespace='test')['resolved'])
        with closing(self.connect()) as db:
            self.assertEqual(pending(db, namespace='test'), [])
            self.assertEqual(db.execute('SELECT status FROM event_dispositions WHERE event_id=?',
                                       (self.value['event_id'],)).fetchone()[0], 'read')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM event_disposition_operations').fetchone()[0], 2)
        self.assertEqual((reopened.stats()['pending'], reopened.stats()['receipt_count']), (1, 0))

    def test_other_channel_cannot_resolve_a_gui_intent(self):
        self.store._prepare_desktop_request(self.value, namespace='test')
        self.store.set_disposition(self.value['event_id'], 'handled', source='cli', operation_id=self.value['operation_id'])
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'desktop_request_completion_unverified'):
            self.store._complete_desktop_request(self.value, namespace='test')
        self.assertEqual(self.store.path.read_bytes(), before)
