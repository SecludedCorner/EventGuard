"""Bounded synthetic export payload; no OS collection or actual user data."""
from contextlib import closing
from pathlib import Path
import hashlib
import json
import sqlite3
import tempfile
import unittest

from eventguard.events.disposition_history_backup import snapshot
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class DispositionHistoryBackupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = EventStore(self.root)
        event = make_synthetic("listener")
        event["event_id"] = "evt-backup-fixture"
        self.store.enqueue(event)

    def read_snapshot(self):
        with closing(sqlite3.connect(self.store.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            return snapshot(db)

    def test_requires_explicit_read_only_transaction(self):
        with closing(sqlite3.connect(self.store.path)) as db:
            with self.assertRaisesRegex(ValueError, "history_snapshot_read_transaction_required"):
                snapshot(db)
            db.execute("BEGIN")
            with self.assertRaisesRegex(ValueError, "history_snapshot_read_transaction_required"):
                snapshot(db)

    def test_legacy_without_table_does_not_create_or_invent_records(self):
        before = self.store.path.read_bytes()
        result = self.read_snapshot()
        self.assertEqual((result["data"]["state"], result["data"]["records"]), ("not_recorded", []))
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_snapshot_preserves_operations_and_unbound_identity_without_mutation(self):
        self.store.set_disposition("evt-backup-fixture", "read", source="gui", operation_id="op-first")
        self.store.set_disposition("evt-backup-fixture", "read", source="mcp", operation_id="op-noop")
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("UPDATE event_disposition_operations SET payload_hash=NULL WHERE operation_id='op-noop'")
            db.commit()
        before = self.store.path.read_bytes()
        result = self.read_snapshot()
        self.assertEqual(result, self.read_snapshot())
        records = result["data"]["records"]
        self.assertEqual([r["operation_id"] for r in records], ["op-first", "op-noop"])
        self.assertIsNone(records[1]["payload_hash"])
        self.assertFalse(records[1]["changed"])
        encoded = json.dumps(result["data"], sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
        self.assertEqual(result["sha256"], hashlib.sha256(encoded).hexdigest())
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))

    def test_corrupt_metadata_is_rejected_without_repair(self):
        self.store.set_disposition("evt-backup-fixture", "read", operation_id="op-first")
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("UPDATE event_disposition_operations SET payload_hash='invalid'")
            db.commit()
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "history_snapshot_invalid"):
            self.read_snapshot()
        self.assertEqual(self.store.path.read_bytes(), before)
