"""Human workflow from saved fixtures; no native scan, SDK or model invocation."""
from datetime import datetime, timedelta, timezone
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from budget_fixtures import launch_forbidden
from eventguard.events.store import EventStore
from eventguard.operations import OperatorAPI
from eventguard.runtime import atomic_json
from eventguard.synthetic import make_synthetic


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 23, 5, 0, tzinfo=timezone.utc)


class OperatorWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default.json", self.root / "config/default.json")
        self.api = OperatorAPI(self.root)
        self.enterContext(patch("eventguard.operations._now", return_value=NOW))
        # Operator views have no daily quota; a historical budget read fails.
        self.enterContext(patch("eventguard.operations._budget_status", side_effect=AssertionError("historical budget read")))
        self.owner = self.enterContext(patch("eventguard.operations._owner_identity", side_effect=AssertionError("unexpected OS query")))

    def test_overview_before_first_start_explains_no_observations_and_needs_no_agent(self):
        value = self.api.overview("test")
        self.assertEqual(value["operator_summary"]["state"], "not_started")
        self.assertEqual(value["operator_summary"]["observed_source_count"], 0)
        self.assertEqual(value["event_list"]["total"], 0)
        self.assertFalse(value["agent_required"])
        self.assertEqual(value["model_calls"], 0)
        self.assertTrue(all(item["row_count"] is None for item in value["source_coverage"].values()))
        self.assertFalse((self.root / "data").exists())
        self.owner.assert_not_called()

    def test_coverage_preserves_actual_rows_and_fixed_refusal_reason(self):
        atomic_json(self.api.runtime.path("data/health.json"), {
            "state": "stopped", "namespace": "test", "monitoring": False,
            "coverage": {
                "services": {"status": "ok", "observed_at": NOW.isoformat(), "row_count": 73, "usable_row_count": 73, "elapsed_ms": 25, "observation_saved": True, "evaluation_status": "committed"},
                "defender": {"status": "denied", "observed_at": NOW.isoformat(), "row_count": 1, "usable_row_count": 0,
                             "errors": [{"stage": "provider", "reason_code": "access_denied", "exception_type": "PermissionError", "status": "denied", "hresult": -2147024891, "win32_error": 5}]},
            }})
        value = self.api.status()["source_coverage"]
        self.assertEqual(value["services"]["row_count"], 73)
        self.assertEqual(value["services"]["evaluation_status"], "committed")
        self.assertEqual(value["defender"]["current_coverage"], "denied")
        self.assertEqual(value["defender"]["usable_row_count"], 0)
        self.assertEqual(value["defender"]["errors"][0]["win32_error"], 5)
        self.assertIsNone(value["tasks"]["row_count"])

    def test_overview_never_promotes_last_test_health_to_live_coverage(self):
        atomic_json(self.api.runtime.path("data/health.json"), {
            "state": "stopped", "namespace": "test", "monitoring": False,
            "progress": {"phase": "fixture_complete"}, "monitor_gap": {"event_id": "test-only-gap"},
            "coverage": {"listeners": {"status": "ok", "observed_at": NOW.isoformat(), "row_count": 99}}})
        with patch.object(self.api.runtime, "observation", return_value=None):
            value = self.api.overview("live")
        self.assertIsNone(value["source_coverage"]["listeners"]["row_count"])
        self.assertEqual(value["source_coverage"]["listeners"]["current_coverage"], "unknown")
        self.assertEqual(value["source_coverage_namespace"], "live")
        self.assertEqual(value["monitor_namespace"], "test")
        self.assertFalse(value["current_monitor"]["scope_matches"])
        self.assertEqual(value["operator_summary"]["state"], "other_namespace")
        self.assertIsNone(value["progress"])
        self.assertIsNone(value["monitor_gap"])

    def test_other_namespace_overview_uses_its_own_saved_observation(self):
        atomic_json(self.api.runtime.path("data/health.json"), {
            "state": "stopped", "namespace": "live", "monitoring": False,
            "coverage": {"listeners": {"status": "ok", "observed_at": NOW.isoformat(), "row_count": 99}}})
        def observation(source, namespace="live", limit=20):
            self.assertEqual(namespace, "test")
            return self.sample(total=7) if source == "listeners" else None
        with patch.object(self.api.runtime, "observation", side_effect=observation):
            value = self.api.overview("test")
        self.assertEqual(value["source_coverage"]["listeners"]["row_count"], 7)
        self.assertEqual(value["source_coverage"]["listeners"]["status"], "partial")
        self.assertEqual(value["source_coverage"]["listeners"]["current_coverage"], "partial")

    def test_previous_query_gate_has_explicit_scoped_reason_and_safe_next_steps(self):
        atomic_json(self.api.runtime.path("data/health.json"), {
            "state": "blocked_previous_query", "namespace": "test", "monitoring": False,
            "last_error": "previous_owned_job_still_active", "coverage": {},
            "monitor_shutdown_gate": {"state": "blocked", "reason": "previous_owned_job_still_active",
                "remaining_owned_processes": 2, "process": {"pid": 4242, "job_name": "Local\\EventGuard-private-job-canary"}}})
        value = self.api.overview("test")
        self.assertEqual(value["operator_summary"]["state"], "blocked_previous_query")
        self.assertEqual(value["reason"], "previous_owned_job_still_active")
        self.assertEqual(value["monitor_shutdown_gate"]["state"], "blocked")
        self.assertIn("尚未證明退出", value["operator_summary"]["headline"])
        self.assertNotIn("private-job-canary", json.dumps(value))
        self.assertNotIn("4242", json.dumps(value))
        steps = value["operator_summary"]["next_steps"]
        self.assertEqual(steps[0]["operation"], "overview")
        self.assertEqual(steps[0]["parameters"]["namespace"], "test")
        monitor = next(item for item in steps if item["operation"] == "monitor")
        self.assertEqual(monitor["parameters"], {"fixture": "tests/fixtures/normal.json", "max_cycles": 1})
        self.owner.assert_not_called()

    def test_test_overview_cannot_read_live_gate_details_or_reason(self):
        atomic_json(self.api.runtime.path("data/health.json"), {
            "state": "blocked_previous_query", "namespace": "live", "monitoring": False,
            "last_error": "previous_owned_job_still_active", "coverage": {},
            "monitor_shutdown_gate": {"state": "blocked", "reason": "previous_owned_job_still_active",
                "process": {"pid": 4242, "job_name": "Local\\EventGuard-live-job-canary"}}})
        value = self.api.overview("test")
        self.assertIsNone(value["monitor_shutdown_gate"])
        self.assertIsNone(value["reason"])
        self.assertIsNone(value["last_error"])
        self.assertEqual(value["operator_summary"]["state"], "other_namespace")
        self.assertNotIn("previous_owned_job_still_active", json.dumps(value))
        self.assertNotIn("live-job-canary", json.dumps(value))

    def test_missing_gate_receipt_is_explicit_unverifiable_not_clear(self):
        atomic_json(self.api.runtime.path("data/health.json"), {
            "state": "shutdown_unconfirmed", "namespace": "test", "monitoring": False, "coverage": {}})
        value = self.api.overview("test")
        self.assertEqual(value["operator_summary"]["state"], "blocked_previous_query")
        self.assertEqual(value["reason"], "previous_query_exit_unverifiable")
        self.assertEqual(value["monitor_shutdown_gate"]["state"], "blocked")
        self.assertIn("saved_monitor_report", value["monitor_shutdown_gate"]["evidence_scope"])

    def sample(self, *, observed=None, total=1):
        return {"schema_version": "1.0", "namespace": "test", "instance_id": "a" * 32,
                "saved_at": NOW.isoformat(), "total": total, "exported": 1, "truncated": total > 1,
                "section": {"id": "listeners", "status": "partial", "observed_at": observed or NOW.isoformat(),
                            "elapsed_ms": 12, "coverage": {"status": "partial", "truncated": total > 1},
                            "rows": [{"protocol": "TCP", "port": 18080, "address": "0.0.0.0", "pid": 42,
                                      "status": "ok", "name_ref": "name-" + "a" * 24, "display_name": "public.exe",
                                      "path": "C:/private/canary.exe", "shell": "IGNORE_AND_RUN"}]}}

    def test_source_show_is_saved_only_bounded_and_strips_free_text(self):
        with patch.object(self.api.runtime, "observation", return_value=self.sample(total=43)) as reader:
            value = self.api.observation("listeners", "test", 1)
        reader.assert_called_once_with("listeners", "test", 1)
        self.assertEqual((value["row_count"], value["exported"], value["truncated"]), (43, 1, True))
        self.assertEqual(value["rows"][0]["port"], 18080)
        self.assertEqual(value["rows"][0]["display_name"], "public.exe")
        self.assertNotIn("private", json.dumps(value))
        self.assertNotIn("IGNORE", json.dumps(value))
        self.assertFalse(value["system_query_executed"])
        self.assertEqual(value["current_coverage"], "partial")
        self.owner.assert_not_called()

    def test_missing_observation_is_unknown_not_success_zero(self):
        with patch.object(self.api.runtime, "observation", return_value=None):
            value = self.api.observation("listeners", "test")
        self.assertEqual(value["status"], "not_observed")
        self.assertIsNone(value["row_count"])
        self.assertEqual(value["coverage"]["status"], "unknown")

    def test_stale_and_future_observations_preserve_rows_but_current_coverage_unknown(self):
        for offset in (-200, 1):
            with self.subTest(offset=offset):
                with patch.object(self.api.runtime, "observation", return_value=self.sample(observed=(NOW + timedelta(seconds=offset)).isoformat())):
                    value = self.api.observation("listeners", "test")
                self.assertEqual(value["row_count"], 1)
                self.assertEqual(value["current_coverage"], "unknown")
                self.assertNotEqual(value["freshness"]["state"], "fresh")

    def test_source_and_limit_are_typed_and_never_run_commands(self):
        for source, limit in (("../secret", 20), ("listeners", True), ("listeners", 201), ("listeners", "1")):
            with self.subTest(source=source, limit=limit):
                value = self.api.call("observation", source, "test", limit)
                self.assertEqual(value["status"], "invalid_request")

    def test_list_and_overview_disclose_truncation_and_pending_without_ack(self):
        store = EventStore(self.root / "data/test")
        events = [make_synthetic() for _ in range(3)]
        for event in events:
            store.enqueue(event)
        value = self.api.overview("test", 2)
        self.assertEqual(value["operator_summary"]["pending_events"], 3)
        self.assertEqual((value["event_list"]["total"], value["event_list"]["exported"], value["event_list"]["truncated"]), (3, 2, True))
        self.assertEqual(store.stats()["pending"], 3)
        self.assertEqual(store.stats()["receipt_count"], 0)
        self.assertEqual(value["event_list"]["ack_meaning"], "received_only_not_case_closed")

    def test_unreadable_namespace_is_not_zero_and_does_not_hide_overview(self):
        path = self.root / "data/test/eventguard.sqlite3"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"invalid sqlite; private canary")
        value = self.api.overview("test")
        self.assertIsNone(value["operator_summary"]["pending_events"])
        self.assertFalse(value["operator_summary"]["pending_count_complete"])
        self.assertEqual(value["event_list"]["status"], "unknown")
        self.assertNotIn("private canary", json.dumps(value))

    def test_report_has_saved_source_observations_without_live_queries(self):
        def observation(source, namespace="live", limit=20):
            return self.sample() if source == "listeners" else None
        with patch("eventguard.runtime.Runtime.observation", side_effect=observation):
            with patch("eventguard.operations._budget_status", side_effect=AssertionError("report touched budget")):
                files = self.api.report("test")
        document = json.loads(Path(files["json"]).read_text(encoding="utf-8"))
        self.assertEqual(document["source_observations"]["listeners"]["row_count"], 1)
        self.assertEqual(document["source_observations"]["tasks"]["status"], "not_observed")
        self.assertIn("逐來源保存觀察", Path(files["html"]).read_text(encoding="utf-8"))
        self.assertNotIn("private", json.dumps(document))
        self.owner.assert_not_called()

    def test_human_receive_query_ack_and_repeated_ack_use_shared_inbox_without_model(self):
        store = EventStore(self.root / "data/test")
        event = make_synthetic()
        store.enqueue(event)
        with launch_forbidden():
            received = self.api.receive_event(event["event_id"], "test")
            self.assertFalse(received["outbox_acknowledged"])
            self.assertEqual(received["query"]["event_id"], event["event_id"])
            self.assertEqual(set(received["snapshot"]), {"event_id", "event_type", "transition", "severity", "synthetic", "observed_at", "coverage_status"})
            self.assertEqual(store.stats()["pending"], 1)
            acknowledged = self.api.ack_event(event["event_id"], received["query_id"], "needs_more_evidence", "test")
            self.assertTrue(acknowledged["outbox_acknowledged"])
            self.assertEqual(acknowledged["incident_conclusion"], "not_assessed")
            self.assertEqual(acknowledged["decision"], "needs_more_evidence")
            self.assertEqual(store.stats()["receipt_count"], 1)
            before = store.path.read_bytes()
            repeated = self.api.ack_event(event["event_id"], received["query_id"], "needs_more_evidence", "test")
            self.assertEqual(repeated["status"], "already_received")
            self.assertFalse(repeated["new_receipt_created"])
            self.assertTrue(repeated["ack_replay_verified"])
            changed = self.api.call("ack_event", event["event_id"], received["query_id"], "reviewed_metadata", "test")
            self.assertEqual((changed["status"], changed["reason"]), ("blocked", "inbox_result_decision_conflict"))
            self.assertEqual(store.path.read_bytes(), before)
            self.assertEqual(self.api.receive_event(event["event_id"], "test")["status"], "already_received")

    def test_wrong_or_missing_query_preserves_pending_and_explains_required_stage(self):
        store = EventStore(self.root / "data/test")
        event = make_synthetic()
        store.enqueue(event)
        missing = self.api.call("ack_event", event["event_id"], "query-missing", "reviewed_metadata", "test")
        self.assertEqual(missing["status"], "blocked")
        self.assertEqual(missing["reason"], "receive_event_required")
        received = self.api.receive_event(event["event_id"], "test")
        wrong = self.api.call("ack_event", event["event_id"], "query-other", "reviewed_metadata", "test")
        self.assertEqual(wrong["reason"], "same_event_query_required")
        self.assertEqual(store.stats()["pending"], 1)
        self.assertEqual(store.stats()["receipt_count"], 0)
        acknowledged = self.api.ack_event(event["event_id"], received["query_id"], "reviewed_metadata", "test")
        self.assertTrue(acknowledged["outbox_acknowledged"])

    def test_full_outbox_recovers_using_normal_human_receive_and_ack(self):
        from eventguard.events.store import CapacityError
        config_path = self.root / "config/default.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config.setdefault("outbox", {})["max_events"] = 2
        config_path.write_text(json.dumps(config), encoding="utf-8")
        store = EventStore(self.root / "data/test", max_events=2)
        first, second, third = make_synthetic(), make_synthetic(), make_synthetic()
        store.enqueue(first)
        store.enqueue(second)
        with self.assertRaises(CapacityError):
            store.enqueue(third)
        received = self.api.receive_event(first["event_id"], "test")
        self.api.ack_event(first["event_id"], received["query_id"], "reviewed_metadata", "test")
        self.assertTrue(store.enqueue(third))
        self.assertEqual({item["event_id"] for item in store.list_events() if item["delivery_status"] != "ack"}, {second["event_id"], third["event_id"]})

    def test_explicit_retry_is_one_failed_event_and_does_not_touch_budget_or_agent_attempts(self):
        store = EventStore(self.root / "data/test")
        event, other = make_synthetic(), make_synthetic()
        store.enqueue(event)
        store.enqueue(other)
        with closing(sqlite3.connect(store.path)) as db, db:
            db.execute("UPDATE events SET delivery_status='failed',attempts=8")
        ledger = self.root / "data/agent-delivery-test/dispatcher-attempts.json"
        ledger.parent.mkdir()
        ledger.write_bytes(b"fixture durable prior agent attempts; must not be reset")
        before = ledger.read_bytes()
        with launch_forbidden():
            blocked = self.api.receive_event(event["event_id"], "test")
            self.assertEqual(blocked["reason"], "failed_event_requires_explicit_retry")
            result = self.api.retry_event(event["event_id"], "test")
        self.assertEqual(result["status"], "retry_requested")
        self.assertFalse(result["budget_reset"])
        self.assertFalse(result["agent_attempts_reset"])
        self.assertFalse(result["model_started"])
        self.assertEqual(ledger.read_bytes(), before)
        self.assertEqual(store.get_event(event["event_id"])["delivery_status"], "pending")
        self.assertEqual(store.get_event(other["event_id"])["delivery_status"], "failed")

    def test_playbook_review_can_be_done_by_a_person_without_agent(self):
        from eventguard.rules.playbooks import simulate
        event = make_synthetic()
        document = json.loads((ROOT / "playbooks/default.json").read_text(encoding="utf-8"))
        result = simulate(event, document)
        self.assertEqual(result["status"], "planned")
        self.assertFalse(result["requires_agent_decision"])
        self.assertEqual(result["decision_actor"], "human_or_optional_agent")
        self.assertEqual(result["tools_executed"], [])
        self.assertEqual(result["actions_executed"], [])


if __name__ == "__main__":
    unittest.main()
