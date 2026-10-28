"""Concurrency and full global revision capacity using synthetic data only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from eventguard.events.catalog import EventCatalog
from eventguard.events.investigation_revision_store import append_revision, RevisionCapacityError
from eventguard.events.investigation_revision import make_revision
from eventguard.events.investigation import build, project
from eventguard.events.store import EventStore
from test_event_investigation import fixture_events, NOW


class RevisionConcurrencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.events = fixture_events()[:2]
        self.store = EventStore(self.root / "data/test")
        for event in self.events:
            self.store.enqueue(event)
        self.catalog = EventCatalog(self.root, "test")
        self.first = self.catalog.investigate("evt-anchor", now=NOW)["case"]

    def test_two_writers_preserve_both_previous_snapshots(self):
        barrier = threading.Barrier(2, timeout=5)
        def save(offset):
            catalog = EventCatalog(self.root, "test")
            barrier.wait()
            return catalog.investigate("evt-anchor", now=(datetime.fromisoformat(NOW) + timedelta(seconds=offset)).isoformat())["case"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            cases = list(pool.map(save, (1, 2)))
        with closing(sqlite3.connect(self.store.path)) as db:
            rows = db.execute("SELECT case_json FROM investigation_revisions ORDER BY revision_id").fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE delivery_status='pending'").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 0)
        history = self.catalog.detail("evt-anchor")["investigation_revisions"]["revisions"]
        latest = self.catalog.detail("evt-anchor")["investigation"]["case"]
        self.assertEqual({entry["case"]["as_of"] for entry in history} | {latest["as_of"]},
                         {self.first["as_of"], *((datetime.fromisoformat(NOW) + timedelta(seconds=n)).isoformat(timespec="microseconds") for n in (1, 2))})
        self.assertTrue(all(entry["evidence_status"] == "saved_snapshot" for entry in history))

    def test_global_256_limit_rejects_without_overwrite(self):
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("BEGIN IMMEDIATE")
            for number in range(16):
                event = dict(self.events[0], event_id="evt-global-" + str(number))
                case = build(project(event, "listeners"), [], as_of=NOW)
                revision = make_revision(case, event, saved_at=1)
                for _ in range(16):
                    append_revision(db, revision, event, available_bytes=1000000)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM investigation_revisions").fetchone()[0], 256)
            new_event = dict(self.events[0], event_id="evt-global-extra")
            case = build(project(new_event, "listeners"), [], as_of=NOW)
            with self.assertRaisesRegex(RevisionCapacityError, "count_capacity"):
                append_revision(db, make_revision(case, new_event, saved_at=1), new_event, available_bytes=1000000)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM investigation_revisions").fetchone()[0], 256)
            db.rollback()
