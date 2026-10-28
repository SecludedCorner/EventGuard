"""Read-only synthetic handling-history projection and corruption controls."""
from contextlib import closing
from pathlib import Path
import sqlite3
import json
import tempfile
import unittest

from eventguard.events.catalog import EventCatalog
from eventguard.events.disposition_history import MAX_HISTORY_PER_EVENT
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.events.disposition_history_store import HistoryConflictError
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

    def test_changed_event_payload_never_inherits_old_handling_history(self):
        self.catalog.set_status("evt-history-read", "read", source="gui", operation_id="original")
        with closing(sqlite3.connect(self.store.path)) as db:
            payload = json.loads(db.execute("SELECT payload FROM events WHERE event_id=?", ("evt-history-read",)).fetchone()[0])
            payload["evidence"]["port"] = 18082
            db.execute("UPDATE events SET payload=?,payload_hash=? WHERE event_id=?",
                       (json.dumps(payload), event_payload_hash(payload), "evt-history-read"))
            db.commit()
        before = self.store.path.read_bytes()
        self.assertEqual(self.catalog.detail("evt-history-read")["handling_history"]["state"], "unknown")
        self.assertEqual(self.store.path.read_bytes(), before)
        with self.assertRaises(HistoryConflictError):
            self.store.set_disposition("evt-history-read", "read", source="gui", operation_id="original")
        self.assertEqual(self.store.stats()["pending"], 1)

    def test_legacy_unbound_rows_remain_unknown_after_lazy_migration(self):
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("CREATE TABLE event_disposition_operations(operation_id TEXT PRIMARY KEY,event_id TEXT,previous_status TEXT,status TEXT,source TEXT,at REAL,changed INTEGER)")
            db.execute("INSERT INTO event_disposition_operations VALUES(?,?,?,?,?,?,?)",
                       ("old", "evt-history-read", "new", "read", "gui", 1000, 1))
            db.commit()
        before = self.store.path.read_bytes()
        self.assertEqual(self.catalog.detail("evt-history-read")["handling_history"]["state"], "unknown")
        self.assertEqual(self.store.path.read_bytes(), before)
        self.store.set_disposition("evt-history-read", "read", source="gui", operation_id="new")
        with closing(sqlite3.connect(self.store.path)) as db:
            self.assertIsNone(db.execute("SELECT payload_hash FROM event_disposition_operations WHERE operation_id='old'").fetchone()[0])
        self.assertEqual(self.catalog.detail("evt-history-read")["handling_history"]["state"], "unknown")
        with self.assertRaises(HistoryConflictError):
            self.store.set_disposition("evt-history-read", "read", source="gui", operation_id="old")

    def test_count_limit_is_explicit_without_claiming_byte_space(self):
        for i in range(MAX_HISTORY_PER_EVENT):
            self.catalog.set_status("evt-history-read", "new", operation_id="noop-" + str(i))
        history = self.catalog.detail("evt-history-read")["handling_history"]
        self.assertEqual(len(history["entries"]), MAX_HISTORY_PER_EVENT)
        self.assertEqual(history["count_capacity"], "full")
        self.assertNotIn("byte_capacity", history)
