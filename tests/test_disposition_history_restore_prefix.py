"""Synthetic prefix-recovery and divergence checks; no real data."""
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from eventguard.events.disposition_history_backup import snapshot
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic
from test_disposition_history_backup_preview import resign


class HistoryRestorePrefixTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        event = make_synthetic("listener")
        event["event_id"] = "evt-restore-prefix"
        self.source = EventStore(root / "source")
        self.target = EventStore(root / "target")
        for store in (self.source, self.target):
            store.enqueue(event)
        self.source.set_disposition(event["event_id"], "read", operation_id="op-prefix-one")
        self.source.set_disposition(event["event_id"], "handled", operation_id="op-prefix-two")
        with closing(sqlite3.connect(self.source.path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            self.backup = snapshot(db, namespace="test")
        self.prefix = deepcopy(self.backup)
        self.prefix["data"]["records"] = self.prefix["data"]["records"][:1]
        resign(self.prefix)

    def history(self):
        with closing(sqlite3.connect(self.target.path)) as db:
            return db.execute("SELECT operation_id,previous_status,status FROM event_disposition_operations ORDER BY rowid").fetchall()

    def test_exact_prefix_appends_only_missing_tail_and_replays(self):
        self.assertEqual(self.target._restore_history(self.prefix, namespace="test")["appended"], 1)
        result = self.target._restore_history(self.backup, namespace="test")
        self.assertEqual((result["already_present"], result["appended"]), (1, 1))
        self.assertEqual(self.history(), [("op-prefix-one", "new", "read"), ("op-prefix-two", "read", "handled")])
        reopened = EventStore(self.target.directory)
        self.assertEqual(reopened._restore_history(self.backup, namespace="test")["appended"], 0)
        self.assertEqual((reopened.stats()["pending"], reopened.stats()["receipt_count"]), (1, 0))

    def test_diverged_target_does_not_erase_or_append_anything(self):
        self.target._restore_history(self.prefix, namespace="test")
        self.target.set_disposition("evt-restore-prefix", "ignored", operation_id="op-newer-target")
        before = self.target.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "not_exact_prefix"):
            self.target._restore_history(self.backup, namespace="test")
        self.assertEqual(self.target.path.read_bytes(), before)
        self.assertEqual([row[0] for row in self.history()], ["op-prefix-one", "op-newer-target"])
        self.assertEqual((self.target.stats()["pending"], self.target.stats()["receipt_count"]), (1, 0))
