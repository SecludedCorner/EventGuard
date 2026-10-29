"""Hash-valid synthetic payloads must still belong to their SQLite row ID."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from eventguard.events.store import EventStore, StoreError, event_payload_hash
from test_store_open_integrity import synthetic_event


class EventRowIdentityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = EventStore(Path(temp.name))
        self.event = synthetic_event('row-anchor')
        self.store.enqueue(self.event)
        self.receipt = {'event_id': 'row-anchor', 'ack_type': 'receiver_persisted',
                        'receipt_id': 'synthetic-receipt', 'receiver_kind': 'local_mock'}

    def corrupt(self):
        other = synthetic_event('different-payload-id')
        with self.store._connect() as db:
            db.execute('UPDATE events SET payload=?,payload_hash=? WHERE event_id=?',
                       (json.dumps(other), event_payload_hash(other), 'row-anchor'))

    def assert_refused_unchanged(self, action):
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(StoreError, 'stored_event_identity_mismatch'):
            action()
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_get_and_list_refuse_hash_valid_foreign_payload(self):
        self.corrupt()
        for action in (lambda: self.store.get_event('row-anchor'), self.store.list_events):
            with self.subTest(action=action):
                self.assert_refused_unchanged(action)

    def test_handling_refuses_before_history_or_disposition_writes(self):
        self.corrupt()
        self.assert_refused_unchanged(lambda: self.store.set_disposition(
            'row-anchor', 'handled', source='gui', operation_id='synthetic-op'))

    def test_ack_refuses_without_receipt_or_delivery_change(self):
        self.corrupt()
        self.assert_refused_unchanged(lambda: self.store.acknowledge('row-anchor', self.receipt))

    def test_ack_replay_refuses_corrupted_source_before_pinning(self):
        self.assertTrue(self.store.acknowledge('row-anchor', self.receipt))
        self.corrupt()
        self.assert_refused_unchanged(lambda: self.store.acknowledge(
            'row-anchor', self.receipt, receiver_finalization=True))

    def test_pump_preserves_bad_evidence_without_sending_or_consuming_attempt(self):
        self.corrupt()
        with self.store._connect() as db:
            before = tuple(db.execute('SELECT payload,payload_hash FROM events').fetchone())
        adapter = Mock(connected=True)
        result = self.store.pump(adapter)
        adapter.send.assert_not_called()
        self.assertEqual((result['attempted'], result['failed'], result['acknowledged']), (0, 1, 0))
        with self.store._connect() as db:
            self.assertEqual(tuple(db.execute('SELECT payload,payload_hash FROM events').fetchone()), before)
            self.assertEqual(tuple(db.execute('SELECT delivery_status,attempts,reason,receipt FROM events').fetchone()),
                             ('failed', 0, 'stored_payload_invalid', None))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0], 0)
