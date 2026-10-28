"""Synthetic transaction and bounded durable operation tests, no OS calls."""
import sqlite3
import unittest

from eventguard.events.disposition_history import MAX_HISTORY_PER_EVENT
from eventguard.events.disposition_history_store import HistoryCapacityError, HistoryConflictError, record_attempt


class DispositionHistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE events(event_id TEXT PRIMARY KEY, delivery_status TEXT, receipt TEXT)")
        self.db.execute("INSERT INTO events VALUES('evt-1','pending',NULL)")
        self.db.commit()
        self.base = {"event_id": "evt-1", "operation_id": "op-1", "previous_status": "new",
                     "status": "read", "source": "gui", "at": 1000}

    def begin(self):
        self.db.execute("BEGIN IMMEDIATE")

    def test_requires_caller_transaction_and_rolls_back_schema_and_pending(self):
        with self.assertRaisesRegex(ValueError, "history_transaction_required"):
            record_attempt(self.db, self.base, available_bytes=1000000, payload_hash="a" * 64)
        self.begin()
        record_attempt(self.db, self.base, available_bytes=1000000, payload_hash="a" * 64)
        self.db.rollback()
        self.assertIsNone(self.db.execute("SELECT 1 FROM sqlite_master WHERE name='event_disposition_operations'").fetchone())
        self.assertEqual(self.db.execute("SELECT delivery_status,receipt FROM events").fetchone(), ("pending", None))

    def test_replay_and_conflict_are_durable_across_transactions(self):
        self.begin()
        first = record_attempt(self.db, self.base, available_bytes=1000000, payload_hash="a" * 64)
        self.db.commit()
        self.begin()
        replay = record_attempt(self.db, {**self.base, "previous_status": "handled"}, available_bytes=0, payload_hash="a" * 64)
        self.assertFalse(first["replayed"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(replay["previous_status"], "new")
        with self.assertRaises(HistoryConflictError):
            record_attempt(self.db, {**self.base, "status": "ignored"}, available_bytes=1000000, payload_hash="a" * 64)
        self.assertEqual(self.db.execute("SELECT count(*) FROM event_disposition_operations").fetchone()[0], 1)
        self.db.rollback()

    def test_noop_consumes_bounded_idempotency_slot_but_is_not_transition(self):
        self.begin()
        value = {**self.base, "status": "new"}
        self.assertFalse(record_attempt(self.db, value, available_bytes=1000000, payload_hash="a" * 64)["changed"])
        self.assertEqual(self.db.execute("SELECT count(*) FROM event_disposition_operations WHERE changed=1").fetchone()[0], 0)
        self.db.commit()

    def test_event_and_byte_limits_fail_without_mutating_old_records(self):
        self.begin()
        with self.assertRaises(HistoryCapacityError):
            record_attempt(self.db, self.base, available_bytes=0, payload_hash="a" * 64)
        self.assertIsNone(self.db.execute("SELECT 1 FROM sqlite_master WHERE name='event_disposition_operations'").fetchone())
        for i in range(MAX_HISTORY_PER_EVENT):
            record_attempt(self.db, {**self.base, "operation_id": "op-"+str(i)}, available_bytes=1000000, payload_hash="a" * 64)
        with self.assertRaises(HistoryCapacityError):
            record_attempt(self.db, {**self.base, "operation_id": "overflow"}, available_bytes=1000000, payload_hash="a" * 64)
        self.assertEqual(self.db.execute("SELECT count(*) FROM event_disposition_operations").fetchone()[0], MAX_HISTORY_PER_EVENT)
        self.assertEqual(self.db.execute("SELECT delivery_status,receipt FROM events").fetchone(), ("pending", None))
        self.db.rollback()


if __name__ == "__main__":
    unittest.main()
