"""Read-only synthetic handling-history projection and corruption controls."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.synthetic import make_synthetic


class DispositionHistoryReadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = EventStore(self.root / "data" / "test")
        event = make_synthetic("listener")
        event["event_id"] = "evt-history-read"
        self.store.enqueue(event)
        self.catalog = EventCatalog(self.root, "test")

    def test_legacy_read_never_creates_table_or_invents_history(self):
        before = self.store.path.read_bytes()
        history = self.catalog.detail("evt-history-read")["handling_history"]
        self.assertEqual(history["state"], "not_recorded")
        self.assertEqual(history["prior_history"], "unknown")
        self.assertEqual(history["entries"], [])
        self.assertEqual(self.store.path.read_bytes(), before)
        with closing(sqlite3.connect(self.store.path)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='event_disposition_operations'").fetchone())

    def test_saved_changes_and_noop_are_bounded_read_only_and_do_not_ack(self):
        self.catalog.set_status("evt-history-read", "read", source="gui", operation_id="first")
        self.catalog.set_status("evt-history-read", "read", source="mcp", operation_id="noop")
        self.catalog.set_status("evt-history-read", "handled", source="cli", operation_id="second")
        before = self.store.path.read_bytes()
        first = self.catalog.detail("evt-history-read")["handling_history"]
        second = self.catalog.detail("evt-history-read")["handling_history"]
        self.assertEqual(first, second)
        self.assertEqual(first["state"], "available")
        self.assertEqual(first["prior_history"], "unknown")
        self.assertEqual([(e["previous_status"], e["status"], e["source"], e["changed"]) for e in first["entries"]],
                         [("new", "read", "gui", True), ("read", "read", "mcp", False), ("read", "handled", "cli", True)])
        self.assertTrue(all("operation_id" not in e for e in first["entries"]))
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))

    def test_corrupt_saved_history_is_unknown_not_repaired(self):
        self.catalog.set_status("evt-history-read", "read", operation_id="first")
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("UPDATE event_disposition_operations SET source='untrusted-source'")
            db.commit()
        before = self.store.path.read_bytes()
        history = self.catalog.detail("evt-history-read")["handling_history"]
        self.assertEqual((history["state"], history["entries"], history["count_capacity"]), ("unknown", [], "unknown"))
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_count_limit_is_explicit_without_claiming_byte_space(self):
        for i in range(32):
            self.catalog.set_status("evt-history-read", "new", operation_id="noop-" + str(i))
        history = self.catalog.detail("evt-history-read")["handling_history"]
        self.assertEqual(len(history["entries"]), 32)
        self.assertEqual(history["count_capacity"], "full")
        self.assertNotIn("byte_capacity", history)
