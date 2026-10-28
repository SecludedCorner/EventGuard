"""Synthetic end-to-end transaction checks for case revision preservation."""
from contextlib import closing
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.catalog import EventCatalog
from eventguard.events.store import CapacityError, EventStore, StoreError
from test_event_investigation import fixture_events, NOW


class RevisionIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root / "data/test")
        self.events = fixture_events()[:2]
        for event in self.events:
            self.store.enqueue(event)
        self.catalog = EventCatalog(self.root, "test")
        self.first = self.catalog.investigate("evt-anchor", now=NOW)["case"]
        self.second_time = (datetime.fromisoformat(NOW) + timedelta(seconds=1)).isoformat()

    def rows(self):
        with closing(sqlite3.connect(self.store.path)) as db:
            current = db.execute("SELECT payload_hash,result,updated_at FROM event_investigations WHERE event_id='evt-anchor'").fetchone()
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='investigation_revisions'").fetchone()
            revisions = db.execute("SELECT payload_hash,case_hash,saved_at,case_json FROM investigation_revisions ORDER BY revision_id").fetchall() if exists else []
            delivery = db.execute("SELECT event_id,delivery_status,receipt FROM events ORDER BY event_id").fetchall()
        return current, revisions, delivery

    def test_update_preserves_original_once_and_replay_is_noop(self):
        before, _, delivery = self.rows()
        self.catalog.investigate("evt-anchor", now=self.second_time)
        current, revisions, after_delivery = self.rows()
        self.assertEqual(len(revisions), 1)
        self.assertEqual(json.loads(revisions[0][3]), self.first)
        self.assertEqual(revisions[0][0], before[0])
        self.assertEqual(revisions[0][2], before[2])
        self.assertNotEqual(json.loads(current[1]), self.first)
        self.assertEqual(delivery, after_delivery)
        self.catalog.investigate("evt-anchor", now=self.second_time)
        self.assertEqual(self.rows(), (current, revisions, after_delivery))

    def test_capacity_failure_rolls_back_prior_case_and_pending(self):
        self.catalog.investigate("evt-anchor", now=self.second_time)
        before = self.rows()
        next_case = dict(json.loads(before[0][1]))
        next_case["as_of"] = (datetime.fromisoformat(NOW) + timedelta(seconds=2)).isoformat()
        from eventguard.events.investigation import build, project, diagnostic_summary
        events = self.events
        next_case = build(project(events[0], "listeners"), [project(events[1], "listeners")],
                          as_of=next_case["as_of"], diagnosis=diagnostic_summary(None))
        with patch.object(self.store, "_used_bytes", return_value=self.store.max_bytes):
            with self.assertRaises(CapacityError):
                self.store.save_investigation("evt-anchor", next_case["anchor_payload_hash"], next_case)
        self.assertEqual(self.rows(), before)

    def test_full_history_fails_closed_with_previous_case_and_delivery_intact(self):
        for seconds in range(1, 17):
            moment = (datetime.fromisoformat(NOW) + timedelta(seconds=seconds)).isoformat()
            self.catalog.investigate("evt-anchor", now=moment)
        before = self.rows()
        self.assertEqual(len(before[1]), 16)
        with self.assertRaises(CapacityError):
            self.catalog.investigate("evt-anchor", now=(datetime.fromisoformat(NOW) + timedelta(seconds=17)).isoformat())
        self.assertEqual(self.rows(), before)

    def test_invalid_previous_case_fails_without_overwriting(self):
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("UPDATE event_investigations SET result='{}'")
            db.commit()
        before = self.rows()
        with self.assertRaisesRegex(StoreError, "investigation_previous_invalid"):
            self.catalog.investigate("evt-anchor", now=self.second_time)
        self.assertEqual(self.rows(), before)

    def test_late_capacity_failure_rolls_back_revision_and_latest(self):
        before = self.rows()
        with patch.object(self.store, "_used_bytes", side_effect=[0, 0, self.store.max_bytes]):
            from eventguard.events.investigation import build, project, diagnostic_summary
            events = self.events
            case = build(project(events[0], "listeners"), [project(events[1], "listeners")],
                         as_of=self.second_time, diagnosis=diagnostic_summary(None))
            with self.assertRaises(CapacityError):
                self.store.save_investigation("evt-anchor", case["anchor_payload_hash"], case)
        self.assertEqual(self.rows(), before)
