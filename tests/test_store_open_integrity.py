"""Synthetic SQLite fixtures only. No collection, processes, network or model."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from eventguard.events.schema import validate_event
from eventguard.events.store import EventStore, StoreError, event_payload_hash


def synthetic_event(identity="evt-store-integrity-1"):
    return validate_event({
        "schema_version": "2.0", "event_id": identity, "host_id": "host-fixture",
        "episode_id": "episode-fixture", "correlation_id": "correlation-fixture", "sequence": 1,
        "event_type": "listener.changed", "transition": "new", "severity": "warning", "synthetic": True,
        "observed_at": "2026-10-24T00:00:00Z", "persisted_at": "2026-10-24T00:00:01Z",
        "evidence": {"protocol": "TCP", "port": 18080, "scope": "loopback"},
        "coverage": {"status": "ok", "gaps": []},
    })


def legacy_store(path, *, invalid_payload=False):
    """The supported legacy schema predates hashes and receiver pinning."""
    path.parent.mkdir(parents=True, exist_ok=True)
    event = synthetic_event()
    with closing(sqlite3.connect(path)) as db:
        with db:
            db.execute("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            db.execute("""CREATE TABLE events(
                event_id TEXT PRIMARY KEY,payload TEXT NOT NULL,delivery_status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,created_at REAL NOT NULL,updated_at REAL NOT NULL,
                next_retry_at REAL,reason TEXT NOT NULL DEFAULT '',lease_until REAL,lease_token TEXT,receipt TEXT)""")
            db.execute("CREATE TABLE receipts(event_id TEXT PRIMARY KEY,receipt TEXT NOT NULL,acked_at REAL NOT NULL)")
            db.execute("INSERT INTO events(event_id,payload,delivery_status,created_at,updated_at) VALUES(?,?,'pending',1,1)",
                       (event["event_id"], "not-json" if invalid_payload else json.dumps(event)))
            db.execute("INSERT INTO meta VALUES('detector_state',?)", (json.dumps({"baseline": "fixture-legacy"}),))
    return event


class StoreOpenIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name) / "outbox"
        self.path = self.directory / "eventguard.sqlite3"

    def assert_failed_open_unchanged(self, reason):
        before = self.path.read_bytes()
        fingerprint = hashlib.sha256(before).hexdigest()
        # Corruption tests need no real-time sleep. The concurrent test below
        # exercises the actual bounded grace period separately.
        with patch("eventguard.events.store.INITIALIZATION_WAIT_SECONDS", 0):
            with self.assertRaisesRegex(StoreError, "^" + reason + "$"):
                EventStore(self.directory)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), fingerprint)

    def test_new_store_is_created_and_normal_restart_preserves_pending(self):
        self.assertFalse(self.path.exists())
        first = EventStore(self.directory, max_events=3)
        event = synthetic_event()
        first.commit_evaluation({"baseline": "fixture-current"}, [event])
        restarted = EventStore(self.directory)
        self.assertEqual(restarted.stats()["pending"], 1)
        self.assertEqual(restarted.stats()["max_events"], 3)
        self.assertEqual(restarted.load_detector_state(), {"baseline": "fixture-current"})
        self.assertEqual(restarted.get_event(event["event_id"])["delivery_status"], "pending")
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as db:
            self.assertEqual(db.execute("PRAGMA auto_vacuum").fetchone()[0], 2)

    def test_truncated_pending_store_is_not_recreated_as_empty(self):
        EventStore(self.directory).enqueue(synthetic_event())
        self.path.write_bytes(b"")  # Deliberate corruption of a synthetic outbox.
        self.assert_failed_open_unchanged("store_schema_unreadable")
        self.assertEqual(self.path.stat().st_size, 0)

    def test_missing_required_table_is_not_recreated(self):
        for table in ("meta", "events", "receipts"):
            with self.subTest(table=table):
                directory = self.directory / table
                store = EventStore(directory)
                store.enqueue(synthetic_event())
                with closing(sqlite3.connect(store.path)) as db:
                    db.execute("DROP TABLE " + table)
                    db.commit()
                before = store.path.read_bytes()
                with self.assertRaisesRegex(StoreError, "^store_schema_unreadable$"):
                    EventStore(directory)
                self.assertEqual(store.path.read_bytes(), before)
                self.assertEqual(hashlib.sha256(store.path.read_bytes()).hexdigest(), hashlib.sha256(before).hexdigest())
                with closing(sqlite3.connect(store.path.as_uri() + "?mode=ro", uri=True)) as db:
                    self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone())

    def test_missing_required_column_is_rejected_without_migration(self):
        legacy_store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("ALTER TABLE events DROP COLUMN receipt")
            db.commit()
        self.assert_failed_open_unchanged("store_schema_unreadable")

    def test_invalid_sqlite_bytes_keep_existing_fixed_error_and_bytes(self):
        self.directory.mkdir()
        self.path.write_bytes(b"invalid synthetic sqlite bytes\x00\xff")
        self.assert_failed_open_unchanged("store_policy_unreadable")

    def test_invalid_policy_is_not_overwritten(self):
        store = EventStore(self.directory)
        store.enqueue(synthetic_event())
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE meta SET value='not-json' WHERE key='storage_policy'")
            db.commit()
        self.assert_failed_open_unchanged("store_policy_unreadable")

    def test_known_legacy_columns_are_migrated_without_losing_pending(self):
        event = legacy_store(self.path)
        migrated = EventStore(self.directory)
        self.assertEqual(migrated.stats()["pending"], 1)
        self.assertEqual(migrated.load_detector_state(), {"baseline": "fixture-legacy"})
        self.assertEqual(migrated.get_event(event["event_id"])["delivery_status"], "pending")
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as db:
            self.assertEqual(db.execute("SELECT payload_hash FROM events").fetchone()[0], event_payload_hash(event))
            self.assertIn("pending_finalization", {row[1] for row in db.execute("PRAGMA table_info(receipts)")})

    def test_failed_legacy_migration_rolls_back_schema_and_payload(self):
        legacy_store(self.path, invalid_payload=True)
        self.assert_failed_open_unchanged("store_initialization_failed")
        with closing(sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)) as db:
            self.assertNotIn("payload_hash", {row[1] for row in db.execute("PRAGMA table_info(events)")})
            self.assertNotIn("pending_finalization", {row[1] for row in db.execute("PRAGMA table_info(receipts)")})
            self.assertEqual(db.execute("SELECT delivery_status,payload FROM events").fetchone(), ("pending", "not-json"))

    def test_initialization_save_failure_rolls_back_policy_and_keeps_pending(self):
        original = EventStore(self.directory, max_events=3)
        event = synthetic_event()
        original.enqueue(event)
        before = self.path.read_bytes()
        initialize = EventStore._initialize_schema

        def fail_after_policy_write(store, db, previous):
            initialize(store, db, previous)
            raise sqlite3.OperationalError("synthetic initialization write failure")

        with patch.object(EventStore, "_initialize_schema", fail_after_policy_write):
            with self.assertRaisesRegex(StoreError, "^store_initialization_failed$"):
                EventStore(self.directory, max_events=2)
        self.assertEqual(self.path.read_bytes(), before)
        restarted = EventStore(self.directory)
        self.assertEqual(restarted.stats()["max_events"], 3)
        self.assertEqual(restarted.get_event(event["event_id"])["delivery_status"], "pending")

    def test_invalid_new_policy_does_not_leave_an_empty_database(self):
        with self.assertRaisesRegex(StoreError, "^invalid_storage_policy$"):
            EventStore(self.directory, max_events=0)
        self.assertFalse(self.path.exists())
        self.assertEqual(EventStore(self.directory).stats()["pending"], 0)

    def test_concurrent_first_open_waits_for_creator_before_classifying_empty_file(self):
        created = threading.Event()
        inspected_empty = threading.Event()
        results, errors = [], []
        connect = sqlite3.connect
        inspect_schema = EventStore._schema_columns
        creator_delayed = [False]

        def delayed_connect(*args, **kwargs):
            db = connect(*args, **kwargs)
            if threading.current_thread().name == "fixture-store-creator" and not creator_delayed[0]:
                creator_delayed[0] = True
                created.set()
                if not inspected_empty.wait(2):
                    db.close()
                    raise AssertionError("synthetic observer did not inspect the creation window")
            return db

        def observed_schema(db):
            value = inspect_schema(db)
            if threading.current_thread().name == "fixture-store-observer" and value is None:
                inspected_empty.set()
            return value

        def open_store():
            try:
                results.append(EventStore(self.directory).stats()["pending"])
            except BaseException as error:
                errors.append(error)

        creator = threading.Thread(target=open_store, name="fixture-store-creator")
        observer = threading.Thread(target=open_store, name="fixture-store-observer")
        with patch("eventguard.events.store.sqlite3.connect", side_effect=delayed_connect), \
             patch.object(EventStore, "_schema_columns", staticmethod(observed_schema)):
            try:
                creator.start()
                self.assertTrue(created.wait(2), "synthetic creator must create its empty file first")
                observer.start()
            finally:
                # Unblock and join only these local fixture threads on failure.
                if not observer.is_alive():
                    inspected_empty.set()
                creator.join(5)
                if observer.ident is not None:
                    observer.join(5)
        self.assertFalse(creator.is_alive(), "synthetic creator thread must exit")
        self.assertFalse(observer.is_alive(), "synthetic observer thread must exit")
        self.assertEqual(errors, [])
        self.assertTrue(inspected_empty.is_set())
        self.assertEqual(sorted(results), [0, 0])
        self.assertEqual(EventStore(self.directory).stats()["pending"], 0)


if __name__ == "__main__":
    unittest.main()
