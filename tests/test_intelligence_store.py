"""Synthetic SQLite contract tests. These do not fetch or start a real agent."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from eventguard.intelligence.store import IntelligenceStore, IntelligenceError, IntelligenceCapacityError


class IntelligenceStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "intelligence.sqlite3"
        self.store = IntelligenceStore(self.path, cooldown_seconds=60)
        self.source = {"id": "rustsec", "interval_seconds": 60, "failure_threshold": 3, "stale_after_seconds": 300}
        self.record = {"ids": ["RUSTSEC-2026-0381"], "component": "synthetic-component", "ecosystem": "cargo",
                       "affected": ["<1.2.3"], "fixes": [], "conditions": {}, "evidence": [],
                       "exploitation": "unknown", "confidence": "high", "withdrawn": False, "synthetic": True,
                       "source_url": "https://example.invalid/advisory"}
        self.assessment = {"status": "possible", "reason_codes": ["version_range_matches"], "asset_refs": ["asset-1"],
                           "evidence": [], "conditions": {"feature": "unknown"}, "fix_available": False}

    def ingest(self, record=None, assessment=None, now=1000, source="rustsec"):
        return self.store.ingest(record or self.record, assessment or self.assessment, source, now)

    def test_initial_possible_is_one_durable_change(self):
        changes = self.ingest()
        self.assertEqual([row["reason"] for row in changes], ["possible_relevance"])
        again = IntelligenceStore(self.path).pending_changes(now=1001)
        self.assertEqual([row["change_id"] for row in again], [changes[0]["change_id"]])
        self.assertTrue(again[0]["synthetic"])

    def test_unknown_and_not_applicable_do_not_claim_safety_or_trigger(self):
        for status in ("unknown", "not_applicable"):
            self.assertEqual(self.ingest(assessment={**self.assessment, "status": status, "asset_refs": []}), [])
        case = self.store.cases()[0]
        self.assertEqual(case["assessment"]["status"], "not_applicable")
        self.assertEqual(self.store.status(1000)["model_calls"], 0)

    def test_unchanged_restart_zero_new_changes(self):
        first = self.ingest()[0]
        self.store.mark_emitted(first["change_id"], "evt-1")
        self.store = IntelligenceStore(self.path)
        self.assertEqual(self.ingest(now=1001), [])
        self.assertEqual(self.store.pending_changes(now=1002), [])

    def test_title_format_fetch_timestamps_aliases_and_order_do_not_trigger(self):
        change = self.ingest()[0]
        self.store.mark_emitted(change["change_id"], "evt-1")
        revised = {**self.record, "title": "changed formatting", "fetched_at": "2099-01-01T00:00:00Z",
                   "updated_at": "2099-01-01T00:00:00Z", "content_hash": "different", "aliases": ["CVE-2026-10000"],
                   "evidence": [{"source_url": "https://example.invalid/repost", "title": "repost"}]}
        self.assertEqual(self.ingest(revised, now=1001), [])
        self.assertEqual(len(self.store.cases()), 1)
        self.assertIn("CVE-2026-10000", self.store.cases()[0]["aliases"])
        self.assertEqual(self.store.cases()[0]["record"]["title"], "changed formatting")

    def test_later_cve_alias_reuses_zdi_case(self):
        zdi = {**self.record, "ids": ["ZDI-CAN-32005"], "component": "connman", "ecosystem": "linux"}
        original = self.ingest(zdi)[0]
        self.store.mark_emitted(original["change_id"], "evt-zdi")
        self.assertEqual(self.ingest({**zdi, "ids": ["CVE-2026-20000"], "aliases": ["ZDI-CAN-32005"]}, now=1001), [])
        self.assertEqual(self.store.cases()[0]["case_id"], original["case_id"])
        self.assertEqual(self.store.event_case("evt-zdi")["record"]["component"], "connman")

    def test_existing_cases_merge_and_old_case_ref_still_resolves(self):
        first = self.ingest()[0]
        other = self.ingest({**self.record, "ids": ["CVE-2026-10000"]}, now=1001, source="cve")[0]
        self.ingest({**self.record, "aliases": ["CVE-2026-10000"]}, now=1002)
        self.assertEqual(len(self.store.cases()), 1)
        self.assertEqual(self.store.advisory(other["case_id"])["case_id"], first["case_id"])
        self.assertEqual(len(self.store.advisory(first["case_id"])["sources"]), 2)

    def test_retraction_and_reactivation_are_durable(self):
        self.ingest()
        changes = self.ingest({**self.record, "withdrawn": True}, now=1001)
        self.assertEqual(changes[0]["reason"], "withdrawn")
        self.assertEqual(self.ingest({**self.record, "withdrawn": True}, now=1002), [])
        self.assertEqual(self.ingest(now=1100)[0]["reason"], "possible_relevance")

    def test_new_withdrawn_unrelated_record_does_not_trigger(self):
        self.assertEqual(self.ingest({**self.record, "withdrawn": True}, {**self.assessment, "status": "not_applicable"}), [])
        self.assertEqual(self.ingest({**self.record, "ids": ["CVE-2026-9999"], "withdrawn": True}, {**self.assessment, "status": "unknown", "asset_refs": []}), [])

    def test_related_component_unknown_range_requires_investigation_without_affected_claim(self):
        assessment = {**self.assessment, "status": "unknown", "reason_codes": ["version_range_unknown"]}
        change = self.ingest(assessment=assessment)[0]
        self.assertEqual((change["reason"], change["coverage_status"]), ("possible_relevance", "unknown"))
        self.assertEqual(self.store.cases()[0]["case_status"], "unknown")
        self.assertEqual(self.ingest(assessment=assessment, now=1001), [])

    def test_rules_can_disable_reasons_and_change_severity_without_commands(self):
        self.store = IntelligenceStore(self.path, event_rules={"enabled_reasons": ["fix_available"], "severity": {"fix_available": "high"}})
        self.assertEqual(self.ingest(), [])
        changes = self.ingest({**self.record, "fixes": [{"version": "1.2.3", "stage": "released"}]},
                              {**self.assessment, "fix_available": True}, now=1001)
        self.assertEqual(changes[0]["severity"], "high")
        reader = IntelligenceStore(self.path, readonly=True)
        self.assertEqual(reader.status(1001)["event_rules"]["enabled_reasons"], ["fix_available"])
        for rules in ({"command": "bad"}, {"enabled_reasons": ["unknown_reason"]}, {"severity": {"fix_available": "run_shell"}}, {"severity": {"fix_available": []}}):
            with self.assertRaisesRegex(IntelligenceError, "invalid_event_rules"):
                IntelligenceStore(self.path, event_rules=rules)

    def test_available_fix_is_not_installation_or_resolution(self):
        self.ingest()
        changes = self.ingest({**self.record, "fixes": [{"version": "1.2.3", "stage": "released"}]},
                              {**self.assessment, "fix_available": True}, now=1001)
        self.assertEqual(changes[0]["reason"], "fix_available")
        self.assertEqual(self.store.cases()[0]["assessment"]["status"], "possible")

    def test_patch_proposed_without_available_release_does_not_trigger_fix(self):
        self.ingest()
        self.assertEqual(self.ingest({**self.record, "fixes": [{"commit": "a" * 40, "stage": "proposed"}]}, now=1001), [])

    def test_exploitation_poc_laboratory_and_in_the_wild_are_distinct(self):
        self.ingest()
        self.assertEqual(self.ingest({**self.record, "exploitation": "poc"}, now=1001), [])
        self.assertEqual(self.ingest({**self.record, "exploitation": "laboratory"}, now=1002), [])
        change = self.ingest({**self.record, "exploitation": "in_the_wild"}, now=1003)[0]
        self.assertEqual((change["reason"], change["severity"]), ("exploitation_confirmed", "high"))

    def test_exposure_transition_is_never_called_safe(self):
        self.ingest()
        change = self.ingest(assessment={**self.assessment, "status": "unknown", "conditions": {"feature": "read_denied"}}, now=1001)[0]
        self.assertEqual(change["reason"], "exposure_changed")
        self.assertEqual(change["coverage_status"], "unknown")

    def test_pending_change_is_immutable_across_outbox_commit_marker_failure(self):
        first = self.ingest()[0]
        second = self.ingest({**self.record, "affected": ["<1.2.4"]}, now=1001)[0]
        self.assertNotEqual(first["change_id"], second["change_id"])
        self.assertEqual(self.store.pending_changes(now=1002), [first])
        self.assertEqual(len(self.store.pending_changes(now=1060)), 2)
        self.store.mark_emitted(first["change_id"], "evt-already-in-outbox")
        self.assertEqual(self.store.pending_changes(now=1060), [second])
        self.assertEqual(self.store.cases()[0]["record"]["affected"], ["<1.2.4"])

    def test_cooldown_defers_instead_of_dropping_changed_evidence(self):
        first = self.ingest()[0]
        self.store.mark_emitted(first["change_id"], "evt-1")
        second = self.ingest({**self.record, "affected": ["<1.2.4"]}, now=1001)[0]
        self.assertNotEqual(first["change_id"], second["change_id"])
        self.assertEqual(self.store.pending_changes(now=1059), [])
        self.assertEqual(self.store.pending_changes(now=1060)[0]["change_id"], second["change_id"])
        self.assertEqual(self.store.status(1002)["deferred_changes"], 1)

    def test_mark_emitted_is_idempotent_not_ack(self):
        first = self.ingest()[0]
        self.store.mark_emitted(first["change_id"], "evt-1")
        self.store.mark_emitted(first["change_id"], "evt-1")
        with self.assertRaisesRegex(IntelligenceError, "change_event_id_conflict"):
            self.store.mark_emitted(first["change_id"], "evt-2")
        self.assertEqual(self.store.status(1001)["ack_meaning"], "received_only_not_remediated")

    def test_fetch_cache_etag_backoff_and_not_modified_survive_restart(self):
        result = {"status": "success", "records": [self.record], "etag": '"etag-1"',
                  "last_modified": "Wed, 21 Oct 2026 12:00:00 GMT", "content_hash": "abc"}
        self.store.record_fetch(self.source, result, 1000)
        self.store = IntelligenceStore(self.path)
        self.assertEqual(self.store.cached_records("rustsec"), [self.record])
        self.assertEqual(self.store.due_sources([self.source], 1059), [])
        self.assertEqual(self.store.due_sources([self.source], 1060), [self.source])
        self.store.record_fetch(self.source, {"status": "not_modified"}, 1060)
        state = self.store.source_state("rustsec", 1060)
        self.assertEqual(state["etag"], '"etag-1"')
        self.assertEqual(state["cached_records"], [self.record])
        self.assertEqual(state["last_success"], "1970-01-01T00:17:40+00:00")
        self.store.record_fetch(self.source, {"status": "failed", "error_code": "http_503"}, 1120)
        self.assertEqual(self.store.cached_records("rustsec"), [self.record])
        self.assertEqual(self.store.source_state("rustsec", 1120)["status"], "failed")

    def test_source_failure_transition_threshold_recovery_and_no_storm(self):
        for now in (1000, 1060):
            self.store.record_fetch(self.source, {"status": "failed", "error_code": "parse_failed"}, now)
        self.assertEqual(self.store.pending_changes(now=1120), [])
        self.store.record_fetch(self.source, {"status": "failed", "error_code": "parse_failed"}, 1120)
        self.assertEqual([row["reason"] for row in self.store.pending_changes(now=1120)], ["source_stale"])
        for now in (1180, 1240, 1300):
            self.store.record_fetch(self.source, {"status": "failed", "error_code": "parse_failed"}, now)
        self.assertEqual(len(self.store.pending_changes(now=1300)), 1)
        self.store.record_fetch(self.source, {"status": "success", "records": []}, 1360)
        self.assertEqual({row["reason"] for row in self.store.pending_changes(now=1360)}, {"source_stale", "recovered"})
        self.assertEqual(self.store.source_state("rustsec", 1360)["freshness"], "fresh")
        self.assertEqual(next(row for row in self.store.pending_changes(now=1360) if row["reason"] == "recovered")["coverage_status"], "ok")

    def test_unimportant_source_failure_is_recorded_without_alert(self):
        source = {**self.source, "important": False, "failure_threshold": 1}
        self.store.record_fetch(source, {"status": "failed", "error_code": "parse_failed", "retry_after_seconds": None}, 1000)
        self.assertEqual(self.store.source_state("rustsec", 1000)["status"], "failed")
        self.assertEqual(self.store.pending_changes(now=1000), [])

    def test_multiple_source_reposts_same_alias_do_not_create_changes_each_round(self):
        self.ingest()
        self.assertEqual(self.ingest(source="official-osv", now=1001), [])
        for now in (1002, 1003):
            self.assertEqual(self.ingest(source="official-osv", now=now), [])
            self.assertEqual(self.ingest(source="rustsec", now=now), [])
        self.assertEqual(len(self.store.pending_changes(now=1100)), 1)
        self.assertEqual(len(self.store.cases()[0]["sources"]), 2)

    def test_fix_repost_source_url_and_order_are_not_new_fix_availability(self):
        record = {**self.record, "fixes": [{"stage": "released", "version": "1.2.3", "source_url": "https://example.invalid/one"}]}
        assessment = {**self.assessment, "fix_available": True}
        self.ingest(record, assessment)
        repost = {**record, "fixes": [{"stage": "released", "version": "1.2.3", "source_url": "https://example.invalid/two"}]}
        self.assertEqual(self.ingest(repost, assessment, source="repost", now=1001), [])
        self.assertEqual(self.ingest(repost, assessment, now=1002), [])
        self.assertEqual(len(self.store.pending_changes(now=1100)), 1)

    def test_multiple_components_same_source_case_have_independent_history(self):
        first = self.ingest()[0]
        second_record = {**self.record, "component": "second-component", "affected": ["<2.0.0"]}
        second = self.ingest(second_record, now=1001)[0]
        self.assertEqual(first["case_id"], second["case_id"])
        for now in (1002, 1003):
            self.assertEqual(self.ingest(now=now), [])
            self.assertEqual(self.ingest(second_record, now=now), [])
        case = self.store.cases()[0]
        self.assertEqual(len(case["sources"]), 2)
        self.assertEqual({item["record"]["component"] for item in case["sources"]}, {"synthetic-component", "second-component"})
        for item in case["sources"]:
            self.assertEqual(len(item["record"]["content_hash"]), 64)
            self.assertIn("fetched_at", item["record"])
        self.ingest(second_record, {**self.assessment, "status": "not_applicable"}, now=1004)
        self.assertEqual(self.store.cases()[0]["case_status"], "possible")
        self.assertEqual(len(self.store.cases()[0]["components"]), 2)

    def test_empty_successful_fetch_is_not_advisory_withdrawal(self):
        self.ingest()
        self.store.record_fetch(self.source, {"status": "success", "records": []}, 1001)
        self.assertFalse(self.store.cases()[0]["record"]["withdrawn"])
        self.assertEqual(self.store.cases()[0]["case_status"], "possible")

    def test_future_source_clock_is_unknown_not_fresh(self):
        self.store.record_fetch(self.source, {"status": "success", "records": []}, 1001)
        self.assertEqual(self.store.source_state("rustsec", 1000)["freshness"], "unknown")

    def test_stale_age_alerts_before_failure_count_threshold(self):
        self.store.record_fetch(self.source, {"status": "success", "records": []}, 1000)
        self.store.record_fetch(self.source, {"status": "failed", "error_code": "timeout"}, 1300)
        self.assertEqual(self.store.pending_changes(now=1300)[0]["reason"], "source_stale")

    def test_retry_after_is_honored_without_fetching(self):
        self.store.record_fetch(self.source, {"status": "failed", "error_code": "http_429", "retry_after_seconds": 7200}, 1000)
        self.assertEqual(self.store.due_sources([self.source], 8199), [])
        self.assertEqual(self.store.due_sources([self.source], 8200), [self.source])

    def test_not_modified_without_cache_is_explicit_failure(self):
        with self.assertRaisesRegex(IntelligenceError, "not_modified_without_cached_success"):
            self.store.record_fetch(self.source, {"status": "not_modified"}, 1000)
        self.assertIsNone(self.store.source_state("rustsec"))

    def test_cached_records_can_be_reprocessed_after_ingest_full(self):
        store = IntelligenceStore(self.path, max_records=1)
        self.ingest()
        second = {**self.record, "ids": ["CVE-2026-9999"]}
        store.record_fetch(self.source, {"status": "success", "records": [second]}, 1000)
        with self.assertRaises(IntelligenceCapacityError):
            store.ingest(second, self.assessment, "rustsec", 1001)
        store.record_fetch(self.source, {"status": "not_modified"}, 1060)
        self.assertEqual(store.cached_records("rustsec"), [second])
        self.assertEqual(len(store.cases()), 1)

    def test_case_capacity_rollback_does_not_lose_first_pending(self):
        self.store = IntelligenceStore(self.path, max_records=1)
        first = self.ingest()[0]
        with self.assertRaisesRegex(IntelligenceCapacityError, "advisory_capacity"):
            self.ingest({**self.record, "ids": ["CVE-2026-9999"]}, now=1001)
        self.assertEqual(len(self.store.cases()), 1)
        self.assertEqual(self.store.pending_changes(now=1002)[0]["change_id"], first["change_id"])

    def test_change_capacity_rolls_back_advisory_update_then_recovers_with_more_capacity(self):
        self.store = IntelligenceStore(self.path, max_changes=1)
        first = self.ingest()[0]
        self.store.mark_emitted(first["change_id"], "evt-1")
        with self.assertRaisesRegex(IntelligenceCapacityError, "change_capacity"):
            self.ingest({**self.record, "withdrawn": True}, now=1001)
        self.assertFalse(self.store.cases()[0]["record"]["withdrawn"])
        self.store = IntelligenceStore(self.path, max_changes=2)
        self.assertEqual(self.ingest({**self.record, "withdrawn": True}, now=1002)[0]["reason"], "withdrawn")

    def test_source_alert_capacity_failure_rolls_back_fetch_state(self):
        self.store = IntelligenceStore(self.path, max_changes=1)
        self.ingest()
        source = {**self.source, "failure_threshold": 1}
        with self.assertRaises(IntelligenceCapacityError):
            self.store.record_fetch(source, {"status": "failed", "error_code": "timeout"}, 1001)
        self.assertIsNone(self.store.source_state(source["id"]))

    def test_database_full_rolls_back_without_raw_exception(self):
        path = Path(self.tmp.name) / "small.sqlite3"
        store = IntelligenceStore(path, max_bytes=64 * 1024)
        record = {**self.record, "evidence": ["x" * 40000]}
        with self.assertRaisesRegex(IntelligenceCapacityError, "database_capacity"):
            store.ingest(record, self.assessment, "rustsec", 1000)
        self.assertEqual(store.cases(), [])
        self.assertEqual(store.pending_changes(now=1001), [])

    def test_write_failure_is_explicit_and_rolls_back(self):
        original = self.store._change
        with patch.object(self.store, "_change", side_effect=sqlite3.OperationalError("synthetic private error")):
            with self.assertRaisesRegex(IntelligenceError, "^database_transaction_failed$"):
                self.ingest()
        self.assertEqual(self.store.cases(), [])
        self.assertEqual(self.ingest()[0]["reason"], "possible_relevance")

    def test_readonly_status_never_rewrites_file_and_rejects_writes(self):
        self.ingest()
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        reader = IntelligenceStore(self.path, readonly=True)
        self.assertEqual(reader.status(1001)["advisories"], 1)
        self.assertEqual(len(reader.cases()), 1)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)
        with self.assertRaisesRegex(IntelligenceError, "read_only_store"):
            reader.ingest(self.record, self.assessment, "rustsec", 1001)
        missing = Path(self.tmp.name) / "absent" / "store.sqlite3"
        with self.assertRaisesRegex(IntelligenceError, "database_not_initialized"):
            IntelligenceStore(missing, readonly=True)
        self.assertFalse(missing.parent.exists())

    def test_capacity_policy_survives_reopen_and_readonly_query(self):
        self.store = IntelligenceStore(self.path, max_records=2, max_changes=3, cooldown_seconds=90)
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        reader = IntelligenceStore(self.path, readonly=True)
        self.assertEqual(reader.status(1000)["capacity"]["max_records"], 2)
        self.assertEqual(reader.status(1000)["capacity"]["max_changes"], 3)
        self.assertEqual(reader.cooldown_seconds, 90)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), before)

    def test_namespace_binding_survives_restart_and_rejects_cross_sink(self):
        self.store.bind_namespace("test", True)
        reopened = IntelligenceStore(self.path)
        reopened.bind_namespace("test", True)
        for namespace, synthetic in (("live", False), ("test", False)):
            with self.assertRaisesRegex(IntelligenceError, "intelligence_namespace_binding_mismatch"):
                reopened.bind_namespace(namespace, synthetic)
        self.assertEqual(reopened.status(1000)["namespace_binding"], {"namespace": "test", "synthetic": True})

    def test_configuration_change_due_clears_headers_and_disables_old_cache_after_failure(self):
        original = {**self.source, "url": "https://example.invalid/old", "adapter": "osv", "tracking_ids": ["RUSTSEC-2026-0381"]}
        self.store.record_fetch(original, {"status": "success", "records": [self.record], "etag": "old", "last_modified": "old-date"}, 1000)
        revised = {**original, "url": "https://example.invalid/new"}
        self.assertEqual(self.store.due_sources([revised], 1001), [revised])
        with self.assertRaisesRegex(IntelligenceError, "not_modified_without_cached_success"):
            self.store.record_fetch(revised, {"status": "not_modified"}, 1001)
        self.store.record_fetch(revised, {"status": "failed", "error_code": "http_503"}, 1001)
        state = self.store.source_state(original["id"], 1002)
        self.assertFalse(state["cache_matches_config"])
        self.assertEqual(state["freshness"], "unknown")
        self.assertEqual(state["cache_status"], "disabled_old_cache")
        self.assertIsNone(state["etag"])
        self.assertIsNone(state["last_modified"])
        self.assertEqual(self.store.cached_records(original["id"]), [])
        self.assertEqual(state["cached_records"], [self.record])
        self.store.record_fetch(revised, {"status": "success", "records": []}, 1061)
        state = self.store.source_state(original["id"], 1062)
        self.assertTrue(state["cache_matches_config"])
        self.assertEqual(state["cache_config"]["url"], revised["url"])
        self.assertIsNone(state["etag"])

    def test_tracking_adapter_changes_invalidate_cache_but_interval_change_does_not(self):
        source = {**self.source, "url": "https://example.invalid/a", "adapter": "osv", "tracking_ids": ["RUSTSEC-2026-0381"]}
        self.store.record_fetch(source, {"status": "success", "records": []}, 1000)
        for revised in ({**source, "adapter": "html"}, {**source, "tracking_ids": ["CVE-2026-9999"]}):
            self.assertEqual(self.store.due_sources([revised], 1001), [revised])
        self.assertEqual(self.store.due_sources([{**source, "interval_seconds": 120}], 1001), [])

    def test_parallel_duplicate_ingest_creates_one_case_and_one_change(self):
        errors = []
        def worker():
            try:
                IntelligenceStore(self.path).ingest(self.record, self.assessment, "rustsec", 1000)
            except Exception as exc:
                errors.append(type(exc).__name__)
        workers = [threading.Thread(target=worker) for unused in range(4)]
        for worker_thread in workers:
            worker_thread.start()
        for worker_thread in workers:
            worker_thread.join(10)
            self.assertFalse(worker_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(self.store.cases()), 1)
        self.assertEqual(len(self.store.pending_changes(now=1001)), 1)

    def test_input_limits_and_safe_reason_codes(self):
        for record in ({**self.record, "ids": "CVE-2026-1"}, {**self.record, "ids": [12]}, {**self.record, "ids": []}, {**self.record, "fixes": None}, {**self.record, "withdrawn": "false"}):
            with self.assertRaises(IntelligenceError):
                self.ingest(record)
        with self.assertRaisesRegex(IntelligenceError, "invalid_identifier"):
            self.store.record_fetch(self.source, {"status": "failed", "error_code": "raw private error\nuser"}, 1000)
        with self.assertRaises(IntelligenceError):
            self.store.status(float("nan"))
        self.assertEqual(self.store.cases(), [])


if __name__ == "__main__":
    unittest.main()
