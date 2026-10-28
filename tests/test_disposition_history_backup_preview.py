"""Identity preview uses only synthetic SQLite data and never writes it."""
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sqlite3
import tempfile
import unittest

from eventguard.events.disposition_history_backup import preview_identity, snapshot
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


def resign(value):
    data = json.dumps(value["data"], sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    value.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    return value


class HistoryBackupPreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = EventStore(Path(temp.name))
        event = make_synthetic("listener")
        event["event_id"] = "evt-preview-synthetic"
        self.store.enqueue(event)
        self.store.set_disposition(event["event_id"], "read", operation_id="op-preview-synthetic")
        with self.read() as db:
            self.backup = snapshot(db, namespace="test")

    def read(self):
        db = sqlite3.connect(self.store.path.as_uri() + "?mode=ro", uri=True)
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        return closing(db)

    def preview(self, value=None, namespace="test"):
        with self.read() as db:
            return preview_identity(db, self.backup if value is None else value, namespace=namespace)

    def test_matching_and_missing_operation_are_read_only(self):
        before = self.store.path.read_bytes()
        result = self.preview()
        self.assertEqual(result["counts"]["already_present"], 1)
        self.assertEqual(result["identity_conflicts"], 0)
        self.assertEqual((result["history_order"], result["target_records"], result["backup_records"]), ("exact_prefix", 1, 1))
        self.assertFalse(result["restore_performed"])
        self.assertFalse(result["restore_authorized"])
        self.assertEqual(before, self.store.path.read_bytes())
        missing = deepcopy(self.backup)
        missing["data"]["records"][0]["operation_id"] = "op-other-synthetic"
        self.assertEqual(self.preview(resign(missing))["counts"]["absent_operation"], 1)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))

    def test_rejects_wrong_or_unknown_scope_and_invalid_digest(self):
        with self.assertRaisesRegex(ValueError, "namespace_unverified"):
            self.preview(namespace="live")
        legacy = deepcopy(self.backup)
        legacy["data"].pop("namespace")
        legacy["data"]["schema_version"] = "1.0"
        with self.assertRaisesRegex(ValueError, "namespace_unverified"):
            self.preview(resign(legacy))
        tampered = deepcopy(self.backup)
        tampered["data"]["namespace"] = "live"
        with self.assertRaisesRegex(ValueError, "integrity_failed"):
            self.preview(tampered)

    def test_unbound_missing_and_mismatched_events_are_not_inferred(self):
        unbound = deepcopy(self.backup)
        unbound["data"]["records"][0]["payload_hash"] = None
        self.assertEqual(self.preview(resign(unbound))["counts"]["unbound"], 1)
        missing = deepcopy(self.backup)
        missing["data"]["records"][0]["event_id"] = "evt-absent-synthetic"
        self.assertEqual(self.preview(resign(missing))["counts"]["event_missing"], 1)
        mismatch = deepcopy(self.backup)
        mismatch["data"]["records"][0]["payload_hash"] = "0" * 64
        self.assertEqual(self.preview(resign(mismatch))["counts"]["event_mismatch"], 1)
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("UPDATE events SET payload='{}'")
            db.commit()
        self.assertEqual(self.preview()["counts"]["event_mismatch"], 1)

    def test_conflicting_operation_is_not_treated_as_replay(self):
        other = deepcopy(self.backup)
        other["data"]["records"][0]["source"] = "gui"
        result = self.preview(resign(other))
        self.assertEqual(result["history_order"], "diverged")
        self.assertEqual(result["counts"]["operation_conflict"], 1)
        self.assertEqual(result["identity_conflicts"], 1)

    def test_requires_query_only_transaction(self):
        with closing(sqlite3.connect(self.store.path)) as db:
            with self.assertRaisesRegex(ValueError, "read_transaction_required"):
                preview_identity(db, self.backup, namespace="test")
