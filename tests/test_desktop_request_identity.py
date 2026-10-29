"""The status write must still match the immutable hash of the saved intent."""
import json
import unittest
from unittest.mock import patch

import test_desktop_handling as fixture
from eventguard.events.store import EventStore, StoreError, event_payload_hash
from eventguard.events.schema import validate_event


class DesktopRequestIdentityTests(unittest.TestCase):
    setUp = fixture.DesktopHandlingTests.setUp

    def test_changed_valid_payload_between_catalog_read_and_write_is_refused(self):
        expected = event_payload_hash(validate_event(self.store.get_event(self.event_id)))
        original = self.store.set_disposition
        def race(store, *args, **kwargs):
            event = validate_event(self.store.get_event(self.event_id))
            event['severity'] = 'info' if event['severity'] != 'info' else 'high'
            with self.store._connect() as db:
                db.execute('UPDATE events SET payload=?,payload_hash=? WHERE event_id=?',
                           (json.dumps(event), event_payload_hash(event), self.event_id))
            return original(*args, **kwargs)
        with patch.object(EventStore, 'set_disposition', race):
            with self.assertRaisesRegex(StoreError, 'event_status_identity_changed'):
                self.catalog.set_status(self.event_id, 'handled', source='gui', operation_id='bound-op', expected_payload_hash=expected)
        self.assertEqual(self.catalog.detail(self.event_id)['status'], 'new')
        self.assertEqual(self.catalog.detail(self.event_id)['handling_history']['entries'], [])
        self.assertEqual((self.store.stats()['pending'], self.store.stats()['receipt_count']), (1, 0))

    def test_matching_identity_retains_replay_semantics_and_invalid_hash_never_writes(self):
        expected = event_payload_hash(validate_event(self.store.get_event(self.event_id)))
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'invalid_expected_payload_hash'):
            self.catalog.set_status(self.event_id, 'read', operation_id='bad-hash', expected_payload_hash='invalid')
        self.assertEqual(self.store.path.read_bytes(), before)
        for status, op in (('read', 'first'), ('handled', 'later')):
            self.catalog.set_status(self.event_id, status, source='gui', operation_id=op, expected_payload_hash=expected)
        replay = self.catalog.set_status(self.event_id, 'read', source='gui', operation_id='first', expected_payload_hash=expected)
        self.assertEqual(replay['status'], 'handled')
        self.assertTrue(replay['history_replayed'])
