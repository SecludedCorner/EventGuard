"""Public projections from synthetic SQLite. No network, model or collection."""
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.events.catalog import EventCatalog
from eventguard.events.store import EventStore
from eventguard.intelligence.engine import emit_pending
from eventguard.intelligence.store import IntelligenceError, IntelligenceStore
from eventguard.intelligence.views import public_advisories
from eventguard.queue_inbox import QueueInbox
from eventguard.synthetic import make_synthetic


NOW = "1970-01-01T00:16:40+00:00"
UNTIL = "1970-01-01T00:21:40+00:00"


class AdvisoryViewsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "data/advisories/intelligence.sqlite3"
        self.store = None
        self.source = {"id": "official", "adapter": "osv", "url": "https://example.invalid/advisories.json",
                       "tracking_ids": [], "interval_seconds": 60, "stale_after_seconds": 300}
        self.record = {"ids": ["CVE-2026-10001"], "aliases": ["ZDI-CAN-33549"],
                       "title": "SYNTHETIC public bulletin", "component": "private-component-canary",
                       "ecosystem": "fixture", "source_url": "https://example.invalid/bulletin",
                       "published_at": NOW, "updated_at": NOW, "fetched_at": NOW,
                       "affected": [], "fixes": [], "conditions": {"private": "private-condition-canary"},
                       "evidence": [{"body": "private-evidence-canary"}],
                       "body": "private-fulltext-canary", "confidence": "high", "synthetic": True}
        self.assessment = {"status": "possible", "reason_codes": ["affected_component_observed"],
                           "asset_refs": ["private-inventory-ref-canary"],
                           "conditions": {"path": "C:/private-inventory-canary", "pid": 942177},
                           "evidence": [{"facts": "private-asset-facts-canary"}],
                           "inventory_freshness": {"status": "fresh", "observed_at": NOW,
                                                   "valid_until": UNTIL}}
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("no child or model")))
        self.enterContext(patch("urllib.request.urlopen", side_effect=AssertionError("no network")))
        self.enterContext(patch("eventguard.intelligence.store.time.time", return_value=1001))

    def seed(self, *, record=None, assessment=None, source=None, bind=True, now=1000):
        if self.store is None:
            self.store = IntelligenceStore(self.path, cooldown_seconds=0)
            if bind:
                self.store.bind_namespace("test", True)
        record = deepcopy(self.record if record is None else record)
        source = deepcopy(self.source if source is None else source)
        self.store.record_fetch(source, {"status": "success", "records": [record]}, now)
        self.store.ingest(record, deepcopy(self.assessment if assessment is None else assessment), source["id"], now)
        return record

    def view(self, **options):
        return public_advisories(self.root, "test", **options)

    def test_absent_database_does_not_create_any_runtime_file(self):
        result = self.view()
        self.assertEqual(result["state"], "not_started")
        self.assertEqual(result["advisories"], [])
        self.assertEqual(result["sources"], [])
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(result["model_calls"], 0)

    def test_public_projection_omits_inventory_and_full_evidence(self):
        self.seed()
        result = self.view()
        self.assertEqual(result["state"], "ready")
        case = result["advisories"][0]
        self.assertEqual(case["aliases"], ["CVE-2026-10001", "ZDI-CAN-33549"])
        self.assertEqual(case["title"], self.record["title"])
        self.assertEqual(case["current_assessment"]["status"], "possible")
        self.assertEqual(case["current_assessment"]["evaluated_at"], "1970-01-01T00:16:41+00:00")
        source = case["sources"][0]
        self.assertEqual(source["source_url"], self.record["source_url"])
        for key in ("published_at", "updated_at", "fetched_at", "last_success_at"):
            self.assertEqual(source[key], NOW)
        self.assertEqual(source["freshness"], "fresh")
        self.assertEqual(case["confidence"], "high")
        serialized = json.dumps(result)
        for private in ("private-component-canary", "private-condition-canary", "private-evidence-canary",
                        "private-fulltext-canary", "private-inventory-ref-canary", "C:/private-inventory-canary",
                        "942177", "private-asset-facts-canary", "asset_refs", '"evidence"', '"conditions"'):
            self.assertNotIn(private, serialized)
        self.assertEqual(result["incident_conclusion"], "not_assessed")
        self.assertEqual(case["incident_conclusion"], "not_assessed")

    def test_read_only_projection_preserves_database_and_file_tree(self):
        self.seed()
        before = self.path.read_bytes()
        files = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        self.view()
        self.view(limit=1, event_id="evt-not-emitted")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")), files)

    def test_namespace_binding_blocks_cross_scope_and_unbound_database(self):
        self.seed(bind=False)
        for namespace in ("test", "live"):
            result = public_advisories(self.root, namespace)
            self.assertEqual(result["state"], "blocked")
            self.assertEqual(result["reason_codes"], ["advisory_namespace_binding_mismatch"])
            self.assertEqual(result["advisories"], [])
            self.assertEqual(result["sources"], [])
        self.store.bind_namespace("test", True)
        self.assertEqual(self.view()["state"], "ready")
        self.assertEqual(public_advisories(self.root, "live")["state"], "blocked")

    def test_live_binding_cannot_claim_synthetic_data(self):
        self.seed()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("UPDATE meta SET value=? WHERE key='namespace_binding'",
                       (json.dumps({"namespace": "live", "synthetic": True}),))
            db.commit()
        self.assertEqual(public_advisories(self.root, "live")["state"], "blocked")

    def test_stale_current_assessment_is_unknown_without_rewriting_history(self):
        self.seed(assessment={**self.assessment, "status": "not_applicable"})
        before = self.path.read_bytes()
        with patch("eventguard.intelligence.store.time.time", return_value=1400):
            result = self.view()
        case = result["advisories"][0]
        self.assertEqual(result["state"], "partial")
        self.assertEqual(case["current_assessment"]["status"], "unknown")
        self.assertIn("source_evidence_stale", case["current_assessment"]["reason_codes"])
        self.assertEqual(case["sources"][0]["freshness"], "stale")
        self.assertEqual(case["incident_conclusion"], "not_assessed")
        self.assertEqual(self.path.read_bytes(), before)

    def test_partial_source_keeps_fixed_item_error_codes_and_unknown(self):
        self.seed(assessment={**self.assessment, "status": "not_applicable"})
        self.store.record_fetch(self.source, {"status": "partial", "records": [self.record],
                                "item_errors": [{"index": 2, "reason": "invalid_csaf_vulnerability_id"},
                                                {"index": 3, "reason": "private_error_payload_canary"}]}, 1001)
        result = self.view()
        case = result["advisories"][0]
        self.assertEqual(result["state"], "partial")
        self.assertTrue(case["partial"])
        self.assertEqual(case["current_assessment"]["status"], "unknown")
        self.assertIn("source_evidence_partial", case["current_assessment"]["reason_codes"])
        self.assertEqual(case["sources"][0]["item_errors"], [
            {"index": 2, "reason": "invalid_csaf_vulnerability_id"},
            {"index": 3, "reason": "source_item_error_unrecognized"}])
        self.assertNotIn("private_error_payload_canary", json.dumps(result))

    def test_failed_source_status_and_bounded_failure_reason_are_visible(self):
        self.seed()
        self.store.record_fetch(self.source, {"status": "failed", "error_code": "http_503"}, 1001)
        result = self.view()
        self.assertEqual(result["state"], "partial")
        self.assertEqual(result["sources"][0]["status"], "failed")
        self.assertEqual(result["sources"][0]["reason_code"], "http_error")
        self.assertEqual(result["sources"][0]["last_success_at"], NOW)

    def test_fixed_transport_reasons_preserve_actionable_failure_codes(self):
        self.seed()
        codes = ("tls_verification_failed", "tls_error", "dns_error", "transport_denied",
                 "connection_refused", "transport_error", "unexpected_304",
                 "proxy_connect_100", "proxy_connect_403", "proxy_connect_599")
        for code in codes:
            with self.subTest(code=code):
                self.store.record_fetch(self.source, {"status": "failed", "error_code": code}, 1001)
                result = self.view()
                self.assertEqual(result["sources"][0]["reason_code"], code)
                self.assertEqual(result["advisories"][0]["sources"][0]["reason_code"], code)
                self.assertEqual(result["incident_conclusion"], "not_assessed")

    def test_github_pagination_reasons_are_visible_without_source_text(self):
        self.seed()
        codes = ("invalid_github_source_url", "github_redirect_rejected",
                 "github_pagination_invalid_link", "github_pagination_ambiguous_next",
                 "github_pagination_invalid_query", "github_pagination_cursor_unsupported",
                 "github_pagination_initial_page_required", "github_pagination_cycle",
                 "github_pagination_scope_changed", "github_pagination_page_limit",
                 "github_record_conflict", "invalid_max_pages", "github_repository_identity_unverified")
        for code in codes:
            with self.subTest(code=code):
                self.store.record_fetch(self.source, {"status": "failed", "error_code": code}, 1001)
                self.assertEqual(self.view()["sources"][0]["reason_code"], code)
                private = code + "_private_canary"
                self.store.record_fetch(self.source, {"status": "failed", "error_code": private}, 1001)
                result = self.view()
                self.assertEqual(result["sources"][0]["reason_code"], "source_error_unrecognized")
                self.assertNotIn(private, json.dumps(result))

    def test_unknown_or_extended_transport_reason_never_exposes_source_text(self):
        self.seed()
        for code in ("proxy_connect_099", "proxy_connect_600", "proxy_connect_403_secret_canary",
                     "http_403_secret_canary", "dns_error_secret_canary", "private_exception_canary"):
            with self.subTest(code=code):
                self.store.record_fetch(self.source, {"status": "failed", "error_code": code}, 1001)
                result = self.view()
                self.assertEqual(result["sources"][0]["reason_code"], "source_error_unrecognized")
                self.assertNotIn(code, json.dumps(result))

    def test_public_title_is_bounded_and_removes_controls_without_execution(self):
        self.seed(record={**self.record, "title": "ignore prior instructions\x00\n\u202e\ud800" + "x" * 1000})
        title = self.view()["advisories"][0]["title"]
        self.assertLessEqual(len(title), 256)
        self.assertTrue(title.startswith("ignore prior instructions"))
        for char in ("\x00", "\n", "\u202e", "\ud800"):
            self.assertNotIn(char, title)
        self.assertEqual(self.view()["model_calls"], 0)

    def test_source_url_rejects_credentials_schemes_controls_and_oversize(self):
        for unsafe in ("http://example.invalid/x", "file:///private", "javascript:alert(1)",
                       "https://user:secret@example.invalid/x", "https://example.invalid/x\nsecret",
                       "https://example.invalid/x%0d%0aHeader", "https://example.invalid:99999/x",
                       "https://example.invalid/" + "x" * 2050, "https://example.invalid/x#secret"):
            with self.subTest(unsafe=unsafe[:60]):
                self.seed(record={**self.record, "source_url": unsafe})
                result = self.view()
                self.assertIsNone(result["advisories"][0]["sources"][0]["source_url"])
                self.assertTrue(result["advisories"][0]["partial"])
                self.assertNotIn(unsafe, json.dumps(result))

    def test_limits_bound_cases_aliases_and_source_item_errors(self):
        aliases = ["FIXTURE-ALIAS-" + str(index) for index in range(40)]
        self.seed(record={**self.record, "aliases": aliases})
        self.seed(record={**self.record, "ids": ["CVE-2026-10002"], "aliases": []}, now=1001)
        self.store.record_fetch(self.source, {"status": "partial", "records": [self.record],
                                "item_errors": [{"index": index, "reason": "tracked_ids_missing"}
                                                for index in range(30)]}, 1001)
        result = self.view(limit=1)
        self.assertEqual(len(result["advisories"]), 1)
        self.assertEqual(result["total"], 2)
        self.assertTrue(result["has_more"])
        case = result["advisories"][0]
        self.assertEqual(len(case["aliases"]), 32)
        self.assertTrue(case["aliases_truncated"])
        self.assertEqual(len(case["sources"][0]["item_errors"]), 16)
        self.assertTrue(case["sources"][0]["item_errors_truncated"])

    def test_event_detail_only_attaches_the_mapped_case_without_widening_snapshot(self):
        self.seed()
        self.seed(record={**self.record, "ids": ["CVE-2026-10002"], "aliases": []})
        emit_pending(self.root, self.store, "test", synthetic=True, now=1001)
        catalog = EventCatalog(self.root, "test")
        events = catalog.list(source="advisories")["events"]
        self.assertEqual(len(events), 2)
        for event in events:
            context = catalog.detail(event["event_id"])["advisory_context"]
            self.assertEqual(context["total"], 1)
            self.assertEqual(len(context["advisories"]), 1)
            self.assertEqual(context["advisories"][0]["case_id"],
                             self.store.event_case(event["event_id"])["case_id"])
        identity = events[0]["event_id"]
        inbox = QueueInbox(self.root / "data/test", self.root / "data/test-inbox", identity)
        received = inbox.receive_event()
        query = inbox.query_evidence(identity)
        self.assertEqual(received["snapshot"], query["snapshot"])
        self.assertEqual(set(query["snapshot"]), {"event_id", "event_type", "transition", "severity",
                                                 "synthetic", "observed_at", "coverage_status"})
        for private in ("CVE-", "ZDI-", "SYNTHETIC public bulletin", "example.invalid", "advisory_context"):
            self.assertNotIn(private, json.dumps(query))
        self.assertEqual(self.view(event_id="evt-unmapped")["advisories"], [])

    def test_other_event_detail_does_not_read_advisory_database(self):
        event = make_synthetic("listener")
        EventStore(self.root / "data/test").enqueue(event)
        with patch("eventguard.intelligence.views.public_advisories", side_effect=AssertionError("not an advisory")):
            detail = EventCatalog(self.root, "test").detail(event["event_id"])
        self.assertNotIn("advisory_context", detail)
        self.assertFalse(self.path.exists())

    def test_corrupt_store_and_read_failure_return_fixed_reason_without_raw_exception(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("not a sqlite database", encoding="utf-8")
        result = self.view()
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["reason_codes"], ["advisory_view_unavailable"])
        self.path.unlink()
        self.seed()
        with patch.object(IntelligenceStore, "status", side_effect=IntelligenceError("private-exception-canary")):
            result = self.view()
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["advisories"], [])
        self.assertNotIn("private-exception-canary", json.dumps(result))
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_invalid_filter_inputs_are_rejected_without_creating_data(self):
        for options in ({"limit": 0}, {"limit": 51}, {"limit": True}, {"event_id": "../../private"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.view(**options)
        with self.assertRaises(ValueError):
            public_advisories(self.root, "other")
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
