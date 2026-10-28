"""Bounded synthetic export payload; no OS collection or actual user data."""
from contextlib import closing
from pathlib import Path
import hashlib
from copy import deepcopy
import json
import sqlite3
import tempfile
import unittest

from eventguard.events.disposition_history_backup import snapshot, verify_snapshot
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
            return snapshot(db, namespace="test")

    def test_requires_explicit_read_only_transaction(self):
        with closing(sqlite3.connect(self.store.path)) as db:
            with self.assertRaisesRegex(ValueError, "history_snapshot_read_transaction_required"):
                snapshot(db, namespace="test")
            db.execute("BEGIN")
            with self.assertRaisesRegex(ValueError, "history_snapshot_read_transaction_required"):
                snapshot(db, namespace="test")

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

    def test_verified_snapshot_rejects_tampering_and_duplicate_operations(self):
        self.store.set_disposition("evt-backup-fixture", "read", operation_id="op-first")
        value = self.read_snapshot()
        self.assertEqual(verify_snapshot(value)["records"], 1)
        changed = deepcopy(value)
        changed["data"]["records"][0]["status"] = "handled"
        with self.assertRaisesRegex(ValueError, "history_backup_integrity_failed"):
            verify_snapshot(changed)
        duplicate = deepcopy(value)
        duplicate["data"]["records"].append(deepcopy(duplicate["data"]["records"][0]))
        with self.assertRaisesRegex(ValueError, "history_backup_invalid"):
            verify_snapshot(duplicate)
        invalid_state = deepcopy(value)
        invalid_state["data"]["state"] = []
        with self.assertRaisesRegex(ValueError, "history_backup_invalid"):
            verify_snapshot(invalid_state)
        invalid_hash = deepcopy(value)
        invalid_hash["sha256"] = "非英文"
        with self.assertRaisesRegex(ValueError, "history_backup_integrity_failed"):
            verify_snapshot(invalid_hash)
        altered = deepcopy(value)
        altered["data"]["records"][0]["changed"] = False
        with self.assertRaisesRegex(ValueError, "history_backup_invalid"):
            verify_snapshot(altered)

    def test_namespace_is_bound_and_legacy_format_remains_unknown(self):
        value = self.read_snapshot()
        self.assertEqual(verify_snapshot(value)["namespace"], "test")
        swapped = deepcopy(value)
        swapped["data"]["namespace"] = "live"
        with self.assertRaisesRegex(ValueError, "history_backup_integrity_failed"):
            verify_snapshot(swapped)
        legacy = deepcopy(value)
        legacy["data"].pop("namespace")
        legacy["data"]["schema_version"] = "1.0"
        encoded = json.dumps(legacy["data"], sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        legacy.update(sha256=hashlib.sha256(encoded).hexdigest(), bytes=len(encoded))
        self.assertEqual(verify_snapshot(legacy)["namespace"], "unknown")

    def test_corrupt_metadata_is_rejected_without_repair(self):
        self.store.set_disposition("evt-backup-fixture", "read", operation_id="op-first")
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("UPDATE event_disposition_operations SET payload_hash='invalid'")
            db.commit()
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "history_snapshot_invalid"):
            self.read_snapshot()
        self.assertEqual(self.store.path.read_bytes(), before)
