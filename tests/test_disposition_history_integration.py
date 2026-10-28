"""Real synthetic EventStore transactions; no native or model calls."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.disposition_history import MAX_HISTORY_ENTRIES, MAX_HISTORY_PER_EVENT
from eventguard.events.disposition_history_store import record_attempt
from eventguard.events.store import CapacityError, EventStore
from eventguard.synthetic import make_synthetic


class DispositionHistoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.directory = self.root / "data" / "test"
        self.store = EventStore(self.directory)
        event = make_synthetic("listener")
        event["event_id"] = "evt-history-fixture"
        self.store.enqueue(event)
        self.event_id = event["event_id"]

    def rows(self):
        with closing(sqlite3.connect(self.store.path)) as db:
            return db.execute("SELECT operation_id,previous_status,status,changed FROM event_disposition_operations ORDER BY operation_id").fetchall()
    def test_reopen_replay_after_intervening_change_does_not_revert(self):
        first = self.store.set_disposition(self.event_id, "read", source="gui", operation_id="op-1")
        self.assertTrue(first["changed"])
        EventStore(self.directory).set_disposition(self.event_id, "handled", source="mcp", operation_id="op-2")
        replay = EventStore(self.directory).set_disposition(self.event_id, "read", source="gui", operation_id="op-1")
        self.assertTrue(replay["history_replayed"])
        self.assertFalse(replay["changed"])
        self.assertEqual(replay["status"], "handled")
        self.assertEqual(self.rows(), [("op-1", "new", "read", 1), ("op-2", "read", "handled", 1)])
        self.assertEqual(self.store.stats()["pending"], 1)
        self.assertEqual(self.store.stats()["receipt_count"], 0)
    def test_replay_succeeds_even_when_no_new_storage_is_available(self):
        self.store.set_disposition(self.event_id, "read", source="gui", operation_id="original")
        self.store.set_disposition(self.event_id, "handled", source="gui", operation_id="later")
        with patch.object(self.store, "_used_bytes", return_value=self.store.max_bytes):
            replay = self.store.set_disposition(self.event_id, "read", source="gui", operation_id="original")
        self.assertTrue(replay["history_replayed"])
        self.assertEqual(replay["status"], "handled")
        self.assertEqual(len(self.rows()), 2)
    def test_unchanged_request_replays_without_reverting_later_state(self):
        self.store.set_disposition(self.event_id, "new", source="gui", operation_id="noop")
        self.store.set_disposition(self.event_id, "read", source="gui", operation_id="change")
        replay = EventStore(self.directory).set_disposition(self.event_id, "new", source="gui", operation_id="noop")
        self.assertTrue(replay["history_replayed"])
        self.assertEqual(replay["status"], "read")
        self.assertEqual(len(self.rows()), 2)
    def test_failure_after_history_insert_rolls_back_schema_and_state(self):
        def fail_after_insert(*args, **kwargs):
            record_attempt(*args, **kwargs)
            raise RuntimeError("synthetic failure")
        with patch("eventguard.events.disposition_history_store.record_attempt", side_effect=fail_after_insert):
            with self.assertRaises(RuntimeError):
                self.store.set_disposition(self.event_id, "read", operation_id="op-fail")
        with closing(sqlite3.connect(self.store.path)) as db:
            for name in ("event_dispositions", "event_disposition_operations"):
                self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone())
            self.assertEqual(db.execute("SELECT delivery_status,receipt FROM events").fetchone(), ("pending", None))
    def test_post_insert_reserve_recheck_rolls_back_history_and_state(self):
        with patch.object(self.store, "_used_bytes", side_effect=[0, 0, self.store.max_bytes]):
            with self.assertRaisesRegex(CapacityError, "event_history_capacity"):
                self.store.set_disposition(self.event_id, "read", operation_id="reserve-test")
        with closing(sqlite3.connect(self.store.path)) as db:
            for name in ("event_dispositions", "event_disposition_operations"):
                self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone())
            self.assertEqual(db.execute("SELECT delivery_status,receipt FROM events").fetchone(), ("pending", None))
    def test_new_application_instance_replays_and_reports_conflict(self):
        from eventguard.application import Application
        def application():
            app = Application(self.root, port=0, fixture="synthetic", auto_start=False, notifications=False)
            self.addCleanup(app.web.close)
            return app
        first = application().set_event_status(self.event_id, "read", source="gui", operation_id="op-app")
        self.assertEqual(first["state"], "event_status_updated")
        self.store.set_disposition(self.event_id, "handled", source="mcp", operation_id="other")
        second = application()
        replay = second.set_event_status(self.event_id, "read", source="gui", operation_id="op-app")
        self.assertTrue(replay["history_replayed"])
        self.assertEqual(replay["status"], "handled")
        conflict = application().set_event_status(self.event_id, "ignored", source="gui", operation_id="op-app")
        self.assertEqual((conflict["state"], conflict["reason"]), ("conflict", "operation_id_conflict"))
        self.assertEqual(len(self.rows()), 2)
    def test_previous_32_record_limit_recovers_without_losing_history(self):
        for i in range(32):
            self.store.set_disposition(self.event_id, "new", operation_id="old-limit-" + str(i))
        before = self.rows()
        result = self.store.set_disposition(self.event_id, "handled", operation_id="recovered")
        self.assertTrue(result["changed"])
        self.assertEqual(len(self.rows()), 33)
        self.assertTrue(all(row in self.rows() for row in before))
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))
    def test_global_count_limit_rejects_without_losing_existing_data(self):
        self.store.set_disposition(self.event_id, "new", operation_id="seed")
        with closing(sqlite3.connect(self.store.path)) as db:
            payload_hash = db.execute("SELECT payload_hash FROM events WHERE event_id=?", (self.event_id,)).fetchone()[0]
            rows = (("global-" + str(i), "other-" + str(i), "new", "read", "gui", 1000, 1, payload_hash)
                    for i in range(MAX_HISTORY_ENTRIES - 1))
            db.executemany("INSERT INTO event_disposition_operations VALUES(?,?,?,?,?,?,?,?)", rows)
            db.commit()
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(CapacityError, "event_history_capacity"):
            self.store.set_disposition(self.event_id, "read", operation_id="global-overflow")
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (1, 0))
    def test_history_capacity_failure_preserves_status_and_pending(self):
        for i in range(MAX_HISTORY_PER_EVENT):
            self.store.set_disposition(self.event_id, "new", operation_id="noop-" + str(i))
        before = self.rows()
        with self.assertRaisesRegex(CapacityError, "event_history_capacity"):
            self.store.set_disposition(self.event_id, "handled", operation_id="over-limit")
        self.assertEqual(self.rows(), before)
        with closing(sqlite3.connect(self.store.path)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='event_dispositions'").fetchone())
            self.assertEqual(db.execute("SELECT delivery_status,receipt FROM events").fetchone(), ("pending", None))
