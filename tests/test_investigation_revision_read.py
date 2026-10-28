"""Revision reads use isolated synthetic events and do not mutate SQLite."""
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import http.client
import json
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.catalog import EventCatalog
from eventguard.events.investigation_revision_read import read_revisions
from eventguard.events.store import CapacityError, EventStore
from eventguard.web import LocalWeb
from test_event_investigation import fixture_events, NOW


class RevisionReadTests(unittest.TestCase):
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

    def read(self):
        with self.catalog._read() as db:
            return read_revisions(db, self.events[0])

    def update(self):
        self.catalog.investigate("evt-anchor", now=(datetime.fromisoformat(NOW) + timedelta(seconds=1)).isoformat())

    def test_legacy_and_readonly_saved_revision(self):
        before = self.store.path.read_bytes()
        self.assertEqual(self.read()["state"], "not_recorded")
        self.assertEqual(self.read()["prior_history"], "unknown")
        self.assertEqual(self.store.path.read_bytes(), before)
        self.update()
        before = self.store.path.read_bytes()
        result = self.read()
        self.assertEqual(result["state"], "available")
        self.assertEqual(result["revisions"][0]["case"], self.first)
        self.assertGreater(result["revisions"][0]["revision_id"], 0)
        self.assertEqual(self.read()["revisions"][0]["revision_id"], result["revisions"][0]["revision_id"])
        self.assertEqual(result["revisions"][0]["evidence_status"], "saved_snapshot")
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (2, 0))

    def test_missing_or_changed_member_remains_unknown(self):
        self.update()
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("UPDATE events SET payload='{}' WHERE event_id='evt-related'")
            db.commit()
        revision = self.read()["revisions"][0]
        self.assertEqual(revision["evidence_status"], "unknown")
        self.assertEqual(revision["changed_event_ids"], ["evt-related"])
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("DELETE FROM events WHERE event_id='evt-related'")
            db.commit()
        revision = self.read()["revisions"][0]
        self.assertEqual(revision["evidence_status"], "unknown")
        self.assertEqual(revision["missing_event_ids"], ["evt-related"])
        self.assertEqual(revision["case"], self.first)

    def test_corrupt_revision_is_unknown_without_repair(self):
        self.update()
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("UPDATE investigation_revisions SET case_hash=?", ("0" * 64,))
            db.commit()
        before = self.store.path.read_bytes()
        self.assertEqual(self.read()["state"], "unknown")
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_detail_and_http_read_are_bounded_and_leave_source_unchanged(self):
        self.assertEqual(self.catalog.detail("evt-anchor")["investigation_revisions"]["state"], "not_recorded")
        self.update()
        before = self.store.path.read_bytes()
        expected = self.catalog.detail("evt-anchor")["investigation_revisions"]
        web = LocalWeb(self.root, "test", port=0, status_provider=lambda: {})
        web.start()
        try:
            with closing(http.client.HTTPConnection("127.0.0.1", web.server.server_port, timeout=5)) as client:
                client.request("GET", "/api/events/evt-anchor")
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                result = json.loads(response.read())
            self.assertEqual(result["investigation_revisions"], expected)
            self.assertEqual(result["investigation_revisions"]["revisions"][0]["case"], self.first)
            self.assertEqual(result["model_calls"], 0)
            self.assertEqual(self.store.path.read_bytes(), before)
        finally:
            self.assertTrue(web.close()["web_thread_exited"])

    def test_http_capacity_error_explains_preserved_investigation(self):
        self.update()
        before = self.store.path.read_bytes()
        web = LocalWeb(self.root, "test", port=0, status_provider=lambda: {})
        web.start()
        try:
            with patch.object(web.catalog, "investigate", side_effect=CapacityError("synthetic")):
                with closing(http.client.HTTPConnection("127.0.0.1", web.server.server_port, timeout=5)) as client:
                    client.request("POST", "/api/events/evt-anchor/investigation", "{}", {
                        "Content-Type": "application/json", "Origin": web.url, "X-EventGuard-CSRF": web.token})
                    response = client.getresponse()
                    self.assertEqual(response.status, 503)
                    self.assertEqual(json.loads(response.read())["error_code"], "investigation_capacity")
            self.assertEqual(self.store.path.read_bytes(), before)
        finally:
            self.assertTrue(web.close()["web_thread_exited"])

    def test_requires_query_only_transaction(self):
        with closing(sqlite3.connect(self.store.path)) as db:
            with self.assertRaisesRegex(ValueError, "read_transaction_required"):
                read_revisions(db, self.events[0])
