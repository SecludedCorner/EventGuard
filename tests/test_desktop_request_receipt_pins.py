"""Synthetic human/receiver pin overlap; each completion releases only itself."""
from pathlib import Path
import tempfile
import unittest

from eventguard.events.store import EventStore, event_payload_hash
from eventguard.events.schema import validate_event
from eventguard.synthetic import make_synthetic


class DesktopRequestReceiptPinTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = EventStore(Path(temp.name)/'data/test', max_events=8,
                               receipt_limit=2, receipt_retention_seconds=1000000)
        self.anchor, self.intent, self.receipt = self.create('anchor', human=True, receiver=True)
        self.old, _, _ = self.create('old')
        self.new, _, _ = self.create('new')
        with self.store._connect() as db:
            for identity, stamp in ((self.anchor, 0), (self.old, 10), (self.new, 20)):
                db.execute('UPDATE receipts SET acked_at=? WHERE event_id=?', (stamp, identity))
            db.execute('UPDATE events SET updated_at=0')

    def create(self, key, *, human=False, receiver=False):
        event = make_synthetic('listener')
        identity = event['event_id'] = 'synthetic-pin-'+key
        self.store.enqueue(event)
        intent = None
        if human:
            intent = {'namespace': 'test', 'event_id': identity, 'status': 'read', 'operation_id': 'human-'+key,
                      'payload_hash': event_payload_hash(validate_event(self.store.get_event(identity)))}
            self.store._prepare_desktop_request(intent, namespace='test')
            self.store.set_disposition(identity, 'read', source='gui', operation_id=intent['operation_id'])
        receipt = {'ack_type': 'receiver_persisted', 'event_id': identity, 'receipt_id': 'mock-'+key,
                   'receiver_kind': 'local_mock', 'wake_state': 'mock_only_no_agent'}
        self.store.acknowledge(identity, receipt, receiver_finalization=receiver)
        return identity, intent, receipt

    def receipt_ids(self):
        with self.store._connect() as db:
            return {row[0] for row in db.execute('SELECT event_id FROM receipts')}

    def test_overlapping_pins_count_once_and_keep_newest_eligible_receipt(self):
        self.store.maintain(now=30)
        self.assertEqual(self.receipt_ids(), {self.anchor, self.new})
        self.assertEqual(self.store.stats()['pending_receiver_finalizations'], 1)
        self.assertIsNotNone(self.store.get_event(self.anchor))

    def test_receiver_completion_does_not_release_human_evidence(self):
        self.assertTrue(self.store.finalize_receiver(self.anchor, self.receipt))
        self.store.maintain(now=2000000)
        self.assertEqual(self.receipt_ids(), {self.anchor})
        self.assertEqual(self.store.stats()['pending_receiver_finalizations'], 0)
        self.assertIsNotNone(self.store.get_event(self.anchor))
        self.store._complete_desktop_request(self.intent, namespace='test')
        self.store.maintain(now=2000000)
        self.assertIsNone(self.store.get_event(self.anchor))
        self.assertEqual(self.receipt_ids(), set())

    def test_human_confirmation_does_not_release_receiver_receipt(self):
        self.store._complete_desktop_request(self.intent, namespace='test')
        self.store.maintain(now=2000000)
        self.assertEqual(self.receipt_ids(), {self.anchor})
        self.assertEqual(self.store.stats()['pending_receiver_finalizations'], 1)
        # Existing receiver pin protects the receipt; payload TTL is separate.
        self.assertTrue(self.store.finalize_receiver(self.anchor, self.receipt))
        self.assertEqual(self.receipt_ids(), set())

    def test_byte_pressure_trims_only_eligible_receipts_and_keeps_both_pins(self):
        self.store._reclaim_completed(30)
        self.assertEqual(self.receipt_ids(), {self.anchor, self.new})
        self.assertIsNotNone(self.store.get_event(self.anchor))
        self.assertEqual(self.store.stats()['pending_receiver_finalizations'], 1)
        self.store._reclaim_completed(30)
        self.assertEqual(self.receipt_ids(), {self.anchor, self.new})
