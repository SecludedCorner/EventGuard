"""Revision diagnosis identity checks use synthetic saved reviews only."""
from contextlib import closing
from datetime import datetime, timedelta
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from eventguard.diagnostics.review import review
from eventguard.events.catalog import EventCatalog
from eventguard.events.investigation import build, project
from eventguard.events.store import EventStore
from eventguard.web import LocalWeb
from test_event_investigation import fixture_events, NOW
from test_investigation_diagnostics import FixtureAPI


class RevisionDiagnosticTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = EventStore(self.root / "data/test")
        for event in fixture_events()[:2]:
            self.store.enqueue(event)
        self.event = self.store.get_event("evt-anchor")
        self.catalog = EventCatalog(self.root, "test")
        self.later = (datetime.fromisoformat(NOW) + timedelta(seconds=2)).isoformat()

    def save_review(self, stamp=NOW):
        result = dict(review(self.event, FixtureAPI(stamp=stamp), refresh=True, now=stamp), namespace="test")
        self.store.save_review("evt-anchor", result["payload_hash"], result)

    def status(self):
        return self.catalog.detail("evt-anchor")["investigation_revisions"]["revisions"][0]["diagnostic_evidence_status"]

    def test_diagnostic_matches_changes_and_missing_remain_distinct(self):
        self.save_review()
        self.catalog.investigate("evt-anchor", now=NOW)
        self.catalog.investigate("evt-anchor", now=self.later)
        self.assertEqual(self.status(), "matched")
        self.save_review(stamp="2026-10-26T08:00:01Z")
        self.assertEqual(self.status(), "changed")
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("DELETE FROM event_reviews WHERE event_id='evt-anchor'")
            db.commit()
        before = self.store.path.read_bytes()
        self.assertEqual(self.status(), "missing")
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (2, 0))

    def test_http_exposes_changed_diagnosis_without_mutation(self):
        self.save_review()
        self.catalog.investigate("evt-anchor", now=NOW)
        self.catalog.investigate("evt-anchor", now=self.later)
        self.save_review(stamp="2026-10-26T08:00:01Z")
        before = self.store.path.read_bytes()
        web = LocalWeb(self.root, "test", port=0, status_provider=lambda: {})
        web.start()
        try:
            with closing(http.client.HTTPConnection("127.0.0.1", web.server.server_port, timeout=5)) as client:
                client.request("GET", "/api/events/evt-anchor")
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                detail = json.loads(response.read())
            prior = detail["investigation_revisions"]["revisions"][0]
            self.assertEqual(prior["evidence_status"], "saved_snapshot")
            self.assertEqual(prior["diagnostic_evidence_status"], "changed")
            self.assertEqual(detail["model_calls"], 0)
            self.assertEqual(self.store.path.read_bytes(), before)
            self.assertEqual((self.store.stats()["pending"], self.store.stats()["receipt_count"]), (2, 0))
        finally:
            self.assertTrue(web.close()["web_thread_exited"])

    def test_legacy_unbound_is_not_guessed(self):
        case = build(project(self.event, "listeners"), [], as_of=NOW)
        self.store.save_investigation("evt-anchor", case["anchor_payload_hash"], case)
        self.catalog.investigate("evt-anchor", now=self.later)
        self.assertEqual(self.status(), "not_bound")
