"""Join validated saved diagnosis metadata; never start DiagnosticAPI queries."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.diagnostics.review import review, validate_saved_review
from eventguard.events.catalog import EventCatalog
from eventguard.events.investigation import build, project, validate_saved
from eventguard.events.store import EventStore, StoreError
from test_event_investigation import fixture_events, NOW


class FixtureAPI:
    def __init__(self, stamp=NOW, empty=False, status="ok"):
        self.stamp, self.empty, self.status = stamp, empty, status

    def query(self, operation, args):
        row = ({"protocol": "TCP", "port": 18080} if operation == "query_listener" else
               {"process_instance_ref": "proc-"+"a"*24, "pid": 4100, "created_at": "2026-10-26T00:00:00Z"})
        return {"status": self.status, "source": "listeners" if operation == "query_listener" else "processes",
                "observed_at": self.stamp, "coverage": {"status": self.status}, "rows": [] if self.empty else [row]}


class InvestigationDiagnosticTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "data/test"
        self.store = EventStore(self.source)
        for event in fixture_events()[:2]:
            self.store.enqueue(event)
        self.event = self.store.get_event("evt-anchor")
        self.catalog = EventCatalog(self.root, "test")
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("no child, native query or model")))

    def save_review(self, **options):
        result = dict(review(self.event, FixtureAPI(**options), refresh=True, now=options.get("stamp", NOW)), namespace="test")
        validate_saved_review(result, self.event)
        self.store.save_review("evt-anchor", result["payload_hash"], result)
        return result

    def test_missing_review_is_explicit_unknown_without_query_or_ack(self):
        with patch("eventguard.diagnostics.api.DiagnosticAPI.query", side_effect=AssertionError("implicit query")):
            value = self.catalog.investigate("evt-anchor", now=NOW)
        context = value["case"]["diagnostic_context"]
        self.assertEqual(context["state"], "missing")
        self.assertEqual(context["gaps"], ["diagnostic_not_saved"])
        self.assertEqual(value["diagnostic_evidence_status"], "missing")
        self.assertEqual(self.store.get_event("evt-anchor")["delivery_status"], "pending")

    def test_valid_same_event_review_join_is_bounded_and_reopen_is_identical(self):
        self.save_review()
        with patch("eventguard.diagnostics.api.DiagnosticAPI.query", side_effect=AssertionError("implicit query")):
            value = self.catalog.investigate("evt-anchor", now=NOW)
            reopened = EventCatalog(self.root, "test").detail("evt-anchor")["investigation"]
        self.assertEqual(value, reopened)
        context = value["case"]["diagnostic_context"]
        self.assertEqual(value["case"]["schema_version"], "1.1")
        self.assertEqual(value["diagnostic_evidence_status"], "matched")
        self.assertEqual(context["gaps"], [])
        self.assertEqual(len(context["observations"]), 2)
        self.assertNotIn('"rows"', json.dumps(context))
        self.assertEqual(context["payload_hash"], value["case"]["anchor_payload_hash"])

    def test_stale_future_empty_and_partial_diagnosis_stay_limited(self):
        for options, expected in (({"stamp": "2026-10-25T00:00:00Z"}, "diagnostic_stale"),
                                  ({"stamp": "2026-10-27T00:00:00Z"}, "diagnostic_in_future"),
                                  ({"empty": True}, "diagnostic_result_missing"),
                                  ({"status": "partial"}, "diagnostic_incomplete")):
            with self.subTest(options=options):
                self.save_review(**options)
                case = self.catalog.investigate("evt-anchor", now=NOW)["case"]
                self.assertIn(expected, case["diagnostic_context"]["gaps"])
                self.assertEqual(case["status"], "limited")
                self.assertEqual(case["incident_conclusion"], "not_assessed")

    def test_review_changed_or_removed_never_rewrites_saved_case(self):
        self.save_review()
        saved = self.catalog.investigate("evt-anchor", now=NOW)
        self.save_review(stamp="2026-10-26T08:00:01Z")
        changed = self.catalog.detail("evt-anchor")["investigation"]
        self.assertEqual(changed["diagnostic_evidence_status"], "changed")
        self.assertEqual(changed["case"], saved["case"])
        with closing(sqlite3.connect(self.store.path)) as db:
            db.execute("DELETE FROM event_reviews WHERE event_id='evt-anchor'")
            db.commit()
        missing = self.catalog.detail("evt-anchor")["investigation"]
        self.assertEqual(missing["diagnostic_evidence_status"], "missing")
        self.assertEqual(missing["case"], saved["case"])

    def test_cross_event_diagnosis_is_rejected_and_prior_case_is_preserved(self):
        result = self.save_review()
        saved = self.catalog.investigate("evt-anchor", now=NOW)
        result["event"]["event_id"] = "evt-related"
        self.store.save_review("evt-anchor", result["payload_hash"], result)
        with self.assertRaisesRegex(ValueError, "saved_review_invalid"):
            self.catalog.investigate("evt-anchor", now=NOW)
        with closing(sqlite3.connect(self.store.path)) as db:
            row = db.execute("SELECT result FROM event_investigations WHERE event_id='evt-anchor'").fetchone()
        self.assertEqual(json.loads(row[0]), saved["case"])
        self.assertEqual(self.store.get_event("evt-anchor")["delivery_status"], "pending")

    def test_review_update_between_read_and_save_is_rejected(self):
        self.save_review()
        saved = self.catalog.investigate("evt-anchor", now=NOW)
        self.save_review(stamp="2026-10-26T08:00:02Z")
        with self.assertRaisesRegex(StoreError, "investigation_diagnostic_changed"):
            self.store.save_investigation("evt-anchor", saved["case"]["anchor_payload_hash"], saved["case"])

    def test_legacy_1_0_case_remains_readable_and_is_not_silently_upgraded(self):
        event = self.store.get_event("evt-anchor")
        case = build(project(event, "listeners"), [], as_of=NOW)
        self.store.save_investigation("evt-anchor", case["anchor_payload_hash"], case)
        value = self.catalog.detail("evt-anchor")["investigation"]
        self.assertEqual(value["case"], case)
        self.assertEqual(value["diagnostic_evidence_status"], "not_bound")
        self.assertNotIn("diagnostic_context", value["case"])

    def test_tampered_diagnostic_count_or_hash_never_grants_trust(self):
        self.save_review()
        case = self.catalog.investigate("evt-anchor", now=NOW)["case"]
        bad = deepcopy(case)
        bad["diagnostic_context"]["observations"][0]["row_count"] = True
        with self.assertRaisesRegex(ValueError, "saved_investigation_invalid"):
            validate_saved(bad, self.event)
        bad = deepcopy(case)
        bad["diagnostic_context"]["payload_hash"] = "a"*64
        with self.assertRaisesRegex(ValueError, "saved_investigation_invalid"):
            validate_saved(bad, self.event)
