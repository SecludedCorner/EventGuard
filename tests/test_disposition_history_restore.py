"""Restore primitive tests with isolated synthetic stores only."""
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.disposition_history_backup import snapshot
from eventguard.events.disposition_history_restore import restore_suffix
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic
from test_disposition_history_backup_preview import resign


class HistoryRestoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        event = make_synthetic("listener")
        event["event_id"] = "evt-restore-synthetic"
        self.source = EventStore(root / "source")
        self.target = EventStore(root / "target")
        for store in (self.source, self.target):
            store.enqueue(event)
        self.source.set_disposition(event["event_id"], "read", operation_id="op-restore-one")
        self.source.set_disposition(event["event_id"], "handled", operation_id="op-restore-two")
        with closing(sqlite3.connect(self.source.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            self.backup = snapshot(db, namespace="test")

    def connect(self):
        return closing(sqlite3.connect(self.target.path))

    def test_import_rollback_commit_and_replay_preserve_pending(self):
        source_before = self.source.path.read_bytes()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            result = restore_suffix(db, self.backup, namespace="test", available_bytes=1000000)
            self.assertEqual((result["appended"], result["already_present"]), (2, 0))
            self.assertTrue(result["caller_commit_required"])
            db.rollback()
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='event_disposition_operations'").fetchone())
            db.execute("BEGIN IMMEDIATE")
            restore_suffix(db, self.backup, namespace="test", available_bytes=1000000)
            db.commit()
            db.execute("BEGIN IMMEDIATE")
            replay = restore_suffix(db, self.backup, namespace="test", available_bytes=0)
            self.assertEqual((replay["appended"], replay["already_present"]), (0, 2))
            db.rollback()
            self.assertEqual(db.execute("SELECT operation_id FROM event_disposition_operations ORDER BY rowid").fetchall(),
                             [("op-restore-one",), ("op-restore-two",)])
        self.assertEqual(self.source.path.read_bytes(), source_before)
        self.assertEqual((self.target.stats()["pending"], self.target.stats()["receipt_count"]), (1, 0))
        self.assertEqual(self.target.get_event("evt-restore-synthetic")["delivery_status"], "pending")

    def test_rejects_scope_unbound_and_changed_event(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(ValueError, "namespace_unverified"):
                restore_suffix(db, self.backup, namespace="live", available_bytes=1000000)
            altered = deepcopy(self.backup)
            altered["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "integrity_failed"):
                restore_suffix(db, altered, namespace="test", available_bytes=1000000)
            unbound = deepcopy(self.backup)
            unbound["data"]["records"][0]["payload_hash"] = None
            with self.assertRaisesRegex(ValueError, "unbound_event"):
                restore_suffix(db, resign(unbound), namespace="test", available_bytes=1000000)
            with self.assertRaisesRegex(ValueError, "history_bytes_capacity"):
                restore_suffix(db, self.backup, namespace="test", available_bytes=0)
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='event_disposition_operations'").fetchone())
            db.execute("UPDATE events SET payload='{}'")
            with self.assertRaisesRegex(ValueError, "identity_unverified"):
                restore_suffix(db, self.backup, namespace="test", available_bytes=1000000)
            db.rollback()

    def test_failed_second_insert_rolls_back_own_savepoint(self):
        from eventguard.events.disposition_history_store import record_attempt
        calls = 0
        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("synthetic_failure")
            return record_attempt(*args, **kwargs)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            with patch("eventguard.events.disposition_history_restore.record_attempt", side_effect=fail_second):
                with self.assertRaisesRegex(ValueError, "synthetic_failure"):
                    restore_suffix(db, self.backup, namespace="test", available_bytes=1000000)
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='event_disposition_operations'").fetchone())
            self.assertTrue(db.in_transaction)
            db.rollback()

    def test_conflicting_history_rejected_without_overwrite(self):
        self.target.set_disposition("evt-restore-synthetic", "handled", operation_id="op-target-other")
        before = self.target.path.read_bytes()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(ValueError, "not_exact_prefix"):
                restore_suffix(db, self.backup, namespace="test", available_bytes=1000000)
            db.rollback()
        self.assertEqual(self.target.path.read_bytes(), before)

    def test_read_only_or_missing_transaction_is_rejected(self):
        with self.connect() as db:
            with self.assertRaisesRegex(ValueError, "write_transaction_required"):
                restore_suffix(db, self.backup, namespace="test", available_bytes=1000000)
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            with self.assertRaisesRegex(ValueError, "write_transaction_required"):
                restore_suffix(db, self.backup, namespace="test", available_bytes=1000000)
