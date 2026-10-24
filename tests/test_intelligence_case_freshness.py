"""Real SQLite and static-file fixtures. No collection, network, model or host."""
from copy import deepcopy
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from eventguard.intelligence.applicability import evaluate
from eventguard.intelligence.inventory import collect_inventory
from eventguard.intelligence.store import IntelligenceStore


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="seconds")


class CaseFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "intelligence.sqlite3"
        self.store = IntelligenceStore(self.path, cooldown_seconds=0)
        self.source = {"id": "official", "adapter": "osv", "url": "https://example.invalid/original",
                       "tracking_ids": ["RUSTSEC-2026-0381"], "interval_seconds": 60,
                       "stale_after_seconds": 300, "failure_threshold": 10}
        self.record = {"ids": ["RUSTSEC-2026-0381"], "component": "webpki-roots", "ecosystem": "crates.io",
                       "affected": [{"package": "webpki-roots", "ecosystem": "crates.io", "patched": [">=1.0.10"]}],
                       "fixes": [], "evidence": [], "conditions": {}, "confidence": "high", "synthetic": True}
        self.assessment = {"status": "not_applicable", "reason_codes": ["version_outside_advisory_range"],
                           "asset_refs": ["asset-one"], "conditions": {}, "fix_available": False,
                           "inventory_freshness": {"status": "fresh", "observed_at": iso(1000), "valid_until": iso(1600), "reason_codes": []}}
        self.enterContext(patch("subprocess.Popen", side_effect=AssertionError("no child or model")))
        self.enterContext(patch("urllib.request.urlopen", side_effect=AssertionError("no network")))

    def seed(self, *, source=None, record=None, assessment=None, now=1000):
        source, record, assessment = source or self.source, record or self.record, assessment or self.assessment
        self.store.record_fetch(source, {"status": "success", "records": [record]}, now)
        self.store.ingest(record, assessment, source["id"], now)
        return self.store.cases(now=now)[0]["case_id"]

    def test_current_exclusion_requires_source_and_inventory_validity(self):
        identity = self.seed()
        case = self.store.advisory(identity, now=1001)
        self.assertEqual(case["case_status"], "not_applicable")
        self.assertEqual(case["current_assessment"]["status"], "not_applicable")
        self.assertEqual(case["historical_case_status"], "not_applicable")
        self.assertEqual(case["assessment"], self.assessment)
        self.assertEqual(case["assessment_scope"], "historical")
        self.assertEqual(case["sources"][0]["assessment"], self.assessment)
        self.assertEqual(case["current_assessment"]["incident_conclusion"], "not_assessed")

    def test_url_adapter_and_tracking_binding_change_then_failure_downgrades_cases(self):
        for update in ({"url": "https://example.invalid/replacement"}, {"adapter": "rustsec"},
                       {"tracking_ids": ["CVE-2026-111943"]}):
            with self.subTest(update=update):
                identity = self.seed()
                changed = {**self.source, **update}
                self.store.record_fetch(changed, {"status": "failed", "error_code": "http_503"}, 1001)
                reader = IntelligenceStore(self.path, readonly=True)
                case = reader.cases(now=1002)[0]
                self.assertEqual(case["case_id"], identity)
                self.assertEqual(case["case_status"], "unknown")
                self.assertIn("source_binding_changed", case["current_assessment"]["reason_codes"])
                self.assertEqual(case["assessment"], self.assessment)
                self.assertEqual(case["historical_case_status"], "not_applicable")

    def test_failure_with_fresh_saved_evidence_does_not_invent_expiration(self):
        identity = self.seed()
        self.store.record_fetch(self.source, {"status": "failed", "error_code": "parse_failed"}, 1001)
        case = self.store.advisory(identity, now=1002)
        self.assertEqual(case["case_status"], "not_applicable")
        self.assertEqual(self.store.source_state("official", 1002)["status"], "failed")

    def test_failure_and_expiration_make_current_unknown_without_changing_history(self):
        identity = self.seed()
        self.store.record_fetch(self.source, {"status": "failed", "error_code": "http_503"}, 1301)
        case = self.store.advisory(identity, now=1302)
        self.assertEqual(case["case_status"], "unknown")
        self.assertIn("source_evidence_stale", case["current_assessment"]["reason_codes"])
        self.assertEqual(case["assessment"], self.assessment)

    def test_reading_after_tracking_stops_recomputes_expiration_without_writing(self):
        identity = self.seed()
        reader = IntelligenceStore(self.path, readonly=True)
        before = self.path.read_bytes()
        self.assertEqual(reader.advisory(identity, now=1299)["case_status"], "not_applicable")
        self.assertEqual(reader.advisory(identity, now=1300)["case_status"], "unknown")
        self.assertEqual(reader.cases(now=1301)[0]["historical_case_status"], "not_applicable")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.path.with_name(self.path.name + "-journal").exists())

    def test_source_recovery_needs_fresh_original_inventory_evidence(self):
        identity = self.seed()
        self.store.record_fetch(self.source, {"status": "failed", "error_code": "http_503"}, 1301)
        self.assertEqual(self.store.advisory(identity, now=1302)["case_status"], "unknown")
        self.store.record_fetch(self.source, {"status": "success", "records": [self.record]}, 1400)
        self.assertEqual(self.store.advisory(identity, now=1401)["case_status"], "not_applicable")
        self.store.record_fetch(self.source, {"status": "not_modified"}, 1599)
        case = self.store.advisory(identity, now=1600)
        self.assertEqual(case["case_status"], "unknown")
        self.assertIn("inventory_evidence_stale", case["current_assessment"]["reason_codes"])
        self.assertEqual(case["assessment"]["inventory_freshness"]["observed_at"], iso(1000))

    def test_recovered_source_with_changed_range_needs_a_new_assessment(self):
        identity = self.seed()
        changed = deepcopy(self.record)
        changed["affected"][0]["patched"] = [">=2.0.0"]
        self.store.record_fetch(self.source, {"status": "success", "records": [changed]}, 1100)
        case = self.store.advisory(identity, now=1101)
        self.assertEqual(case["case_status"], "unknown")
        self.assertIn("source_assertion_not_current", case["current_assessment"]["reason_codes"])
        possible = {**self.assessment, "status": "possible"}
        self.store.ingest(changed, possible, "official", 1101)
        self.assertEqual(self.store.advisory(identity, now=1102)["case_status"], "possible")

    def test_empty_source_success_does_not_withdraw_or_keep_an_old_exclusion_current(self):
        identity = self.seed()
        self.store.record_fetch(self.source, {"status": "success", "records": []}, 1100)
        case = self.store.advisory(identity, now=1101)
        self.assertEqual(case["case_status"], "unknown")
        self.assertFalse(case["record"].get("withdrawn", False))
        self.assertEqual(case["historical_case_status"], "not_applicable")

    def test_valid_possible_dominates_stale_other_source_but_stale_cannot_prove_exclusion(self):
        identity = self.seed()
        other = {**self.source, "id": "other-official", "url": "https://example.invalid/other"}
        possible = {**self.assessment, "status": "possible"}
        self.seed(source=other, assessment=possible, now=1250)
        case = self.store.advisory(identity, now=1301)
        self.assertEqual(case["case_status"], "possible")
        self.assertIn("source_evidence_stale", case["current_assessment"]["reason_codes"])
        self.store.ingest(self.record, self.assessment, other["id"], 1301)
        case = self.store.advisory(identity, now=1302)
        self.assertEqual(case["case_status"], "unknown")
        self.assertEqual(case["historical_case_status"], "not_applicable")

    def test_all_current_sources_excluded_and_unknown_component_is_not_hidden(self):
        identity = self.seed()
        other = {**self.source, "id": "second", "url": "https://example.invalid/second"}
        second = {**self.record, "component": "webpki-root-certs"}
        self.seed(source=other, record=second, now=1050)
        self.assertEqual(self.store.advisory(identity, now=1051)["case_status"], "not_applicable")
        self.store.ingest(second, {**self.assessment, "status": "unknown"}, "second", 1052)
        self.assertEqual(self.store.advisory(identity, now=1053)["case_status"], "unknown")

    def test_old_assessment_without_inventory_validity_is_historical_only(self):
        assessment = {key: value for key, value in self.assessment.items() if key != "inventory_freshness"}
        identity = self.seed(assessment=assessment)
        case = self.store.advisory(identity, now=1001)
        self.assertEqual(case["case_status"], "unknown")
        self.assertIn("inventory_freshness_unknown", case["current_assessment"]["reason_codes"])
        self.assertEqual(case["assessment"], assessment)

    def test_future_inventory_time_cannot_supply_current_exclusion(self):
        assessment = deepcopy(self.assessment)
        assessment["inventory_freshness"]["observed_at"] = iso(1002)
        identity = self.seed(assessment=assessment)
        self.assertEqual(self.store.advisory(identity, now=1001)["case_status"], "unknown")

    def test_current_projection_preserves_changes_and_event_lookup(self):
        possible = {**self.assessment, "status": "possible"}
        identity = self.seed(assessment=possible)
        change = self.store.pending_changes(now=1000)[0]
        self.store.mark_emitted(change["change_id"], "event-fixture")
        with closing(sqlite3.connect(self.path)) as db:
            before = db.execute("SELECT * FROM changes").fetchall()
        reader = IntelligenceStore(self.path, readonly=True)
        case = reader.event_case("event-fixture", now=1301)
        self.assertEqual(case["case_id"], identity)
        self.assertEqual(case["case_status"], "unknown")
        self.assertEqual(case["historical_case_status"], "possible")
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT * FROM changes").fetchall(), before)

    def test_actual_static_lock_inventory_supplies_configured_validity_without_model_fields(self):
        lock = self.root / "Cargo.lock"
        lock.write_text('version=3\n[[package]]\nname="webpki-roots"\nversion="1.0.10"\n', encoding="utf-8")
        snapshot = collect_inventory({"inventory": {"paths": [str(lock)], "max_age_seconds": 120}}, now=iso(1000))
        assessed = evaluate(self.record, snapshot, now=iso(1000))
        self.assertEqual(assessed["status"], "not_applicable")
        self.assertEqual(assessed["inventory_freshness"]["valid_until"], iso(1120))
        identity = self.seed(assessment=assessed)
        self.assertEqual(self.store.advisory(identity, now=1119)["case_status"], "not_applicable")
        case = self.store.advisory(identity, now=1120)
        self.assertEqual(case["case_status"], "unknown")
        self.assertIn("inventory_evidence_stale", case["current_assessment"]["reason_codes"])

    def test_rereading_asserted_facts_does_not_refresh_the_original_asset_deadline(self):
        facts = self.root / "approved-facts.json"
        facts.write_text(json.dumps({"assets": [{"ecosystem": "rust", "component": "webpki-roots", "version": "1.0.10",
            "facts": {"observed_at": iso(1000), "max_age_seconds": 60}}]}), encoding="utf-8")
        config = {"inventory": {"paths": [{"path": str(facts), "kind": "facts"}], "max_age_seconds": 120}}
        for now in (1050, 1059):
            snapshot = collect_inventory(config, now=iso(now))
            assessed = evaluate(self.record, snapshot, now=iso(now))
            self.assertEqual(assessed["inventory_freshness"]["observed_at"], iso(1000))
            self.assertEqual(assessed["inventory_freshness"]["valid_until"], iso(1060))
        expired = evaluate(self.record, collect_inventory(config, now=iso(1061)), now=iso(1061))
        self.assertEqual(expired["status"], "unknown")
        self.assertEqual(expired["inventory_freshness"]["status"], "stale")

    def test_undated_asserted_facts_and_invalid_inventory_ttl_are_unknown(self):
        facts = self.root / "approved-facts.json"
        facts.write_text(json.dumps({"assets": [{"ecosystem": "rust", "component": "webpki-roots", "version": "1.0.10"}]}), encoding="utf-8")
        config = {"inventory": {"paths": [{"path": str(facts), "kind": "facts"}]}}
        snapshot = collect_inventory(config, now=iso(1000))
        self.assertIsNone(snapshot["assets"][0]["observed_at"])
        assessed = evaluate(self.record, snapshot, now=iso(1000))
        self.assertEqual(assessed["status"], "unknown")
        self.assertEqual(assessed["inventory_freshness"]["status"], "unknown")
        config["inventory"]["max_age_seconds"] = "120"
        self.assertEqual(collect_inventory(config, now=iso(1000))["status"], "unknown")

    def test_disabled_source_does_not_supply_a_current_exclusion(self):
        identity = self.seed()
        disabled = {**self.source, "enabled": False}
        self.store.record_fetch(disabled, {"status": "failed", "error_code": "tracking_disabled"}, 1001)
        case = self.store.advisory(identity, now=1002)
        self.assertEqual(case["case_status"], "unknown")
        self.assertIn("source_tracking_disabled", case["current_assessment"]["reason_codes"])


if __name__ == "__main__":
    unittest.main()
