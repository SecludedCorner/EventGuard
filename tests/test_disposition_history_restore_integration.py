"""Synthetic EventStore transaction integration for append-only recovery."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.disposition_history_backup import snapshot
from eventguard.events.store import CapacityError, EventStore
from eventguard.synthetic import make_synthetic


class HistoryRestoreIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        event = make_synthetic("listener")
        event["event_id"] = "evt-restore-integration"
        self.source = EventStore(root / "source")
        self.target = EventStore(root / "target")
        for store in (self.source, self.target):
            store.enqueue(event)
        self.source.set_disposition(event["event_id"], "read", operation_id="op-restore-integration")
        with closing(sqlite3.connect(self.source.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            self.backup = snapshot(db, namespace="test")

    def test_internal_restore_survives_reopen_and_keeps_idempotency(self):
        before = self.source.path.read_bytes()
        result = self.target._restore_history(self.backup, namespace="test")
        self.assertEqual(result["appended"], 1)
        self.assertFalse(result["caller_commit_required"])
        reopened = EventStore(self.target.directory)
        self.assertEqual(reopened._restore_history(self.backup, namespace="test")["appended"], 0)
        replay = reopened.set_disposition("evt-restore-integration", "read", operation_id="op-restore-integration")
        self.assertTrue(replay["history_replayed"])
        self.assertFalse(replay["changed"])
        self.assertEqual(replay["status"], "new")
        self.assertEqual((reopened.stats()["pending"], reopened.stats()["receipt_count"]), (1, 0))
        self.assertEqual(self.source.path.read_bytes(), before)

    def test_late_capacity_failure_rolls_back_all_insertions(self):
        before = self.target.path.read_bytes()
        with patch.object(self.target, "_used_bytes", side_effect=[0, self.target.max_bytes]):
            with self.assertRaisesRegex(CapacityError, "history_restore_capacity"):
                self.target._restore_history(self.backup, namespace="test")
        self.assertEqual(self.target.path.read_bytes(), before)
        with closing(sqlite3.connect(self.target.path)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='event_disposition_operations'").fetchone())
        self.assertEqual((self.target.stats()["pending"], self.target.stats()["receipt_count"]), (1, 0))

    def test_initial_capacity_failure_never_creates_history(self):
        before = self.target.path.read_bytes()
        with patch.object(self.target, "_used_bytes", return_value=self.target.max_bytes):
            with self.assertRaisesRegex(CapacityError, "history_restore_capacity"):
                self.target._restore_history(self.backup, namespace="test")
        self.assertEqual(self.target.path.read_bytes(), before)
