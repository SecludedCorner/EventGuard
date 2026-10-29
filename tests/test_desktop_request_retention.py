"""Synthetic ACK is independent of an unresolved human intent's retention."""
from pathlib import Path
import tempfile
import unittest

from eventguard.events.catalog import EventCatalog
from eventguard.events.schema import validate_event
from eventguard.events.store import EventStore, CapacityError, StoreError, event_payload_hash
from eventguard.synthetic import make_synthetic


class DesktopRequestRetentionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = EventStore(self.root/'data/test', max_events=1,
                               acked_retention_seconds=10, receipt_retention_seconds=10)
        event = make_synthetic('listener')
        event['event_id'] = 'synthetic-human-intent-pin'
        self.store.enqueue(event)
        self.intent = {'namespace': 'test', 'event_id': event['event_id'], 'status': 'read',
                       'operation_id': 'synthetic-pending-human',
                       'payload_hash': event_payload_hash(validate_event(self.store.get_event(event['event_id'])))}
        self.store._prepare_desktop_request(self.intent, namespace='test')
        self.store.set_disposition(event['event_id'], 'read', source='gui', operation_id=self.intent['operation_id'])
        self.store.acknowledge(event['event_id'], {'ack_type': 'receiver_persisted', 'event_id': event['event_id'],
            'receipt_id': 'synthetic-local-mock-receipt', 'receiver_kind': 'local_mock', 'wake_state': 'mock_only_no_agent'})

    def test_ttl_keeps_event_receipt_and_original_key_until_human_receipt_confirmed(self):
        with self.store._connect() as db:
            db.execute('UPDATE events SET updated_at=0')
            db.execute('UPDATE receipts SET acked_at=0')
        self.store.maintain(now=20)
        reopened = EventStore(self.store.directory)
        self.assertIsNotNone(reopened.get_event(self.intent['event_id']))
        detail = EventCatalog(self.root, 'test').detail(self.intent['event_id'])
        self.assertEqual(detail['pending_handling_requests']['requests'], [self.intent])
        self.assertEqual((reopened.stats()['ack'], reopened.stats()['receipt_count']), (1, 1))
        reopened._complete_desktop_request(self.intent, namespace='test')
        reopened.maintain(now=20)
        self.assertIsNone(reopened.get_event(self.intent['event_id']))
        self.assertEqual(reopened.stats()['receipt_count'], 0)

    def test_count_pressure_refuses_new_event_without_losing_unresolved_anchor(self):
        before = self.store.path.read_bytes()
        event = make_synthetic('listener')
        event['event_id'] = 'synthetic-would-evict-anchor'
        with self.assertRaises(CapacityError):
            self.store.enqueue(event)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertIsNotNone(self.store.get_event(self.intent['event_id']))

    def test_byte_reclaim_keeps_pinned_ack_payload_and_receipt(self):
        before = self.store.path.read_bytes()
        self.assertEqual(self.store._reclaim_completed(20), 0)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()['ack'], self.store.stats()['receipt_count']), (1, 1))

    def test_unknown_journal_blocks_retention_without_reset_or_partial_deletion(self):
        with self.store._connect() as db:
            db.execute('ALTER TABLE desktop_status_requests ADD COLUMN unexpected TEXT')
            db.execute('UPDATE events SET updated_at=0')
            db.execute('UPDATE receipts SET acked_at=0')
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(StoreError, 'desktop_request_retention_unverified'):
            self.store.maintain(now=20)
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertIsNotNone(self.store.get_event(self.intent['event_id']))
