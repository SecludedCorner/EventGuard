"""Synthetic local SQLite/files only; no provider, child, model or agent proof."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.schema import validate_event
from eventguard.events.store import CapacityError, EventStore, StoreError, event_payload_hash
from eventguard.queue_inbox import QueueInbox, QueueInboxError


def event(identity):
    return {"schema_version": "2.0", "event_id": identity, "host_id": "synthetic-finalization-host",
            "episode_id": "synthetic-finalization", "correlation_id": "synthetic-finalization", "sequence": 1,
            "event_type": "listener.changed", "transition": "new", "severity": "warning", "synthetic": True,
            "observed_at": "2026-10-23T00:00:00Z", "persisted_at": "2026-10-23T00:00:00Z",
            "evidence": {"protocol": "TCP", "port": 18080}, "coverage": {"status": "unknown", "gaps": []}}


def receipt(identity):
    return {"ack_type": "receiver_persisted", "event_id": identity, "receipt_id": "synthetic-receipt-"+identity}


class InboxRetentionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.state = self.root/"source", self.root/"inbox"

    def prepare(self, **policy):
        self.store = EventStore(self.source, **policy)
        self.store.enqueue(event("old"))
        self.inbox = QueueInbox(self.source, self.state, "old")
        self.inbox.receive_event()
        self.query = self.inbox.query_evidence("old")

    def fail_completion(self):
        original = self.inbox._immutable
        def fail(path, value):
            if path.name.startswith("completed-"):
                raise QueueInboxError("synthetic_completion_write_failure")
            return original(path, value)
        with patch.object(self.inbox, "_immutable", side_effect=fail):
            with self.assertRaisesRegex(QueueInboxError, "synthetic_completion_write_failure"):
                self.inbox.ack_event("old", self.query["query_id"], "reviewed_metadata")
        self.assertTrue(self.inbox._path("snapshot", "old").exists())
        self.assertFalse(self.inbox._path("completed", "old").exists())
        self.assertEqual(self.store.stats()["pending_receiver_finalizations"], 1)

    def stored_receipt(self, identity):
        with self.store._connect() as db:
            row = db.execute("SELECT * FROM receipts WHERE event_id=?", (identity,)).fetchone()
            return dict(row) if row else None

    def receive_next_and_verify_old(self):
        self.store.enqueue(event("next"))
        expected_hash = event_payload_hash(validate_event(event("next")))
        restarted = QueueInbox(self.source, self.state, "next")
        self.assertEqual(restarted.receive_event()["event_id"], "next")
        self.assertEqual(event_payload_hash(validate_event(self.store.get_event("next"))), expected_hash)
        self.assertEqual(self.store.get_event("next")["delivery_status"], "pending")
        old = QueueInbox(self.source, self.state, "old")
        self.assertEqual(old.query_evidence("old"), self.query)
        with patch.object(old.store, "acknowledge", side_effect=AssertionError("must not ACK twice")):
            self.assertTrue(old.ack_event("old", self.query["query_id"], "reviewed_metadata")["outbox_acknowledged"])
        self.assertTrue(old.acknowledged("old"))
        self.assertEqual(self.store.stats()["pending_receiver_finalizations"], 0)
        self.assertFalse(old._path("snapshot", "old").exists())
        return old

    def test_completion_failure_then_zero_ttl_retains_proof_and_restarts_same_query(self):
        self.prepare(acked_retention_seconds=0, receipt_retention_seconds=0)
        self.fail_completion()
        before = self.stored_receipt("old")
        self.store.maintain()
        self.assertIsNone(self.store.get_event("old"))
        self.assertEqual(self.stored_receipt("old"), before)
        self.receive_next_and_verify_old()
        self.assertIsNone(self.stored_receipt("old"), "Only the completed file permits expiry after finalization")

    def test_finalize_failure_keeps_completed_and_triple_then_maintenance_repairs(self):
        self.prepare(acked_retention_seconds=0, receipt_retention_seconds=0)
        with patch.object(self.inbox.store, "finalize_receiver", side_effect=StoreError("synthetic_finalize_failure")):
            with self.assertRaisesRegex(QueueInboxError, "outbox_finalization_failed_completed_preserved"):
                self.inbox.ack_event("old", self.query["query_id"], "needs_more_evidence")
        self.assertTrue(self.inbox._path("completed", "old").exists())
        for stage in ("snapshot", "query", "result"):
            self.assertTrue(self.inbox._path(stage, "old").exists())
        self.store.maintain()
        self.assertEqual(self.store.stats()["pending_receiver_finalizations"], 1)
        restarted = QueueInbox(self.source, self.state, "old")
        restarted.maintain()
        self.assertEqual(restarted.query_evidence("old"), self.query)
        with patch.object(restarted.store, "acknowledge", side_effect=AssertionError("must not ACK twice")):
            self.assertTrue(restarted.ack_event("old", self.query["query_id"], "needs_more_evidence")["outbox_acknowledged"])
        self.assertEqual(self.store.stats()["pending_receiver_finalizations"], 0)
        self.assertFalse(restarted._path("snapshot", "old").exists())

    def test_completed_only_record_releases_a_persistent_pin_after_restart(self):
        self.prepare(acked_retention_seconds=0, receipt_retention_seconds=0)
        with patch.object(self.inbox.store, "finalize_receiver", side_effect=StoreError("synthetic_finalize_failure")):
            with self.assertRaises(QueueInboxError):
                self.inbox.ack_event("old", self.query["query_id"], "reviewed_metadata")
        # Simulate a retained completion with no redundant triple from an older
        # cleanup order; a durable completion must still release its own pin.
        for stage in ("snapshot", "query", "result"):
            self.inbox._path(stage, "old").unlink()
        self.store.maintain()
        self.receive_next_and_verify_old()

    def test_count_pressure_does_not_rotate_unfinalized_receipt(self):
        self.prepare(max_events=2, receipt_limit=2, acked_retention_seconds=0)
        self.fail_completion()
        before = self.stored_receipt("old")
        for index in range(6):
            identity = "count-"+str(index)
            self.store.enqueue(event(identity))
            self.store.acknowledge(identity, receipt(identity))
            self.assertEqual(self.stored_receipt("old"), before)
            self.assertLessEqual(self.store.stats()["receipt_count"], 2)
        self.receive_next_and_verify_old()

    def test_byte_pressure_rotates_only_finalized_receipts(self):
        self.prepare(max_events=3, max_bytes=65536)
        self.fail_completion()
        before = self.stored_receipt("old")
        for index in range(80):
            identity = "bytes-"+str(index)
            self.store.enqueue(event(identity))
            self.store.acknowledge(identity, receipt(identity))
            self.assertEqual(self.stored_receipt("old"), before)
            self.assertLessEqual(self.store.path.stat().st_size, 65536)
        self.assertGreater(int(self.store.stats()["receipt_rotation"].get("pressure_rotated_receipts", 0)), 0)
        self.receive_next_and_verify_old()

    def test_finalization_limit_rolls_back_second_ack_then_release_recovers(self):
        store = EventStore(self.source, receipt_limit=1)
        for identity in ("first", "second"):
            store.enqueue(event(identity))
        self.assertTrue(store.acknowledge("first", receipt("first"), receiver_finalization=True))
        pending = store.get_event("second")
        with self.assertRaisesRegex(CapacityError, "receiver_finalization_capacity_pending_preserved"):
            store.acknowledge("second", receipt("second"), receiver_finalization=True)
        self.assertEqual(store.get_event("second"), pending)
        self.assertEqual(store.stats()["receipt_count"], 1)
        self.assertTrue(store.finalize_receiver("first", receipt("first")))
        self.assertTrue(store.acknowledge("second", receipt("second"), receiver_finalization=True))
        self.assertEqual(store.stats()["pending_receiver_finalizations"], 1)

    def test_mismatched_finalization_never_releases_original_proof_or_changes_ack(self):
        store = EventStore(self.source)
        store.enqueue(event("first"))
        store.acknowledge("first", receipt("first"), receiver_finalization=True)
        before = store.get_event("first")
        with self.assertRaisesRegex(StoreError, "ack_receipt_identity_conflict"):
            store.finalize_receiver("first", {**receipt("first"), "receipt_id": "different"})
        self.assertEqual(store.stats()["pending_receiver_finalizations"], 1)
        store.acknowledge("first", receipt("first"), receiver_finalization=True)
        self.assertEqual(store.get_event("first"), before)
        self.assertTrue(store.finalize_receiver("first", receipt("first")))
        self.assertFalse(store.finalize_receiver("first", receipt("first")))
        self.assertFalse(store.finalize_receiver("missing", receipt("missing")))
        self.assertIsNone(store.get_event("missing"))
        self.assertEqual(store.get_event("first"), before)

    def test_legacy_receipts_schema_migrates_without_changing_original_ack(self):
        store = EventStore(self.source)
        store.enqueue(event("first"))
        store.acknowledge("first", receipt("first"))
        before = store.get_event("first")
        with store._connect() as db:
            db.execute("ALTER TABLE receipts DROP COLUMN pending_finalization")
        reopened = EventStore(self.source)
        self.assertEqual(reopened.get_event("first"), before)
        self.assertEqual(reopened.stats()["pending_receiver_finalizations"], 0)
        self.assertTrue(reopened.acknowledge("first", receipt("first"), receiver_finalization=True))
        self.assertEqual(reopened.stats()["pending_receiver_finalizations"], 1)

    def test_already_lost_legacy_proof_stays_blocked_instead_of_inventing_ack(self):
        self.prepare()
        self.fail_completion()
        # A pre-fix crash may already have lost both source and receipt. A
        # saved result alone is only ACK intent, never original ACK evidence.
        with self.store._connect() as db:
            db.execute("DELETE FROM events WHERE event_id='old'")
            db.execute("DELETE FROM receipts WHERE event_id='old'")
        self.store.enqueue(event("next"))
        restarted = QueueInbox(self.source, self.state, "next")
        with self.assertRaisesRegex(QueueInboxError, "bound_event_missing"):
            restarted.receive_event()
        self.assertFalse(self.inbox._path("completed", "old").exists())
        self.assertTrue(self.inbox._path("result", "old").exists())
        self.assertEqual(self.store.get_event("next")["delivery_status"], "pending")


if __name__ == "__main__":
    unittest.main()
