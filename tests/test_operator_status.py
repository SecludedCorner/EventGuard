"""Operator freshness and reporting fixtures; no OS inventory or model calls."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import copy
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from eventguard.collectors.contract import evidence
from eventguard.events.schema import validate_event
from eventguard.events.store import EventStore, event_payload_hash
from eventguard.operations import OperatorAPI, _budget_status
from eventguard.runtime import Runtime, atomic_json
from eventguard.synthetic import make_synthetic


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc)
CREATED = "2026-10-23T00:00:00.000000+00:00"


class OperatorStatusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default.json", self.root / "config/default.json")
        self.runtime, self.api = Runtime(self.root), OperatorAPI(self.root)
        # Operator status has no daily quota; a historical budget read fails.
        self.enterContext(patch("eventguard.operations._budget_status",
                                side_effect=AssertionError("historical budget read")))
        self.enterContext(patch("eventguard.operations._now", return_value=NOW))
        self.identity = self.enterContext(patch("eventguard.operations._owner_identity", return_value={
            "pid": 4242, "created_at": CREATED, "state": "alive"}))

    def health(self, **changes):
        value = {"state": "running", "monitoring": True, "namespace": "test", "pid": 4242,
                 "process_created_at": CREATED, "instance_id": "a" * 32,
                 "heartbeat_at": NOW.isoformat(), "coverage": {}}
        value.update(changes)
        atomic_json(self.runtime.path("data/health.json"), value)
        return value

    def owner(self, **changes):
        value = {"pid": 4242, "process_created_at": CREATED, "instance_id": "a" * 32}
        value.update(changes)
        atomic_json(self.runtime.path("data/monitor-owner.json"), value)

    def test_empty_status_is_readonly_and_does_not_query_any_pid(self):
        result = self.api.status()
        self.assertEqual(result["last_report"]["state"], "not_started")
        self.assertEqual(result["current_monitor"]["state"], "not_started")
        self.assertEqual(result["namespaces"]["test"]["state"], "not_created")
        self.assertNotIn("agent_budget", result)
        self.assertFalse((self.root / "data").exists())
        self.identity.assert_not_called()

    def test_current_owner_and_fresh_heartbeat_are_separate_from_last_report(self):
        saved = self.health(healthy=False, last_error="queue_capacity_or_storage_failure")
        self.owner()
        result = self.api.status()
        self.assertEqual(result["health"], saved)
        self.assertEqual(result["last_report"], saved)
        self.assertEqual(result["current_monitor"]["state"], "running_verified")
        self.assertTrue(result["current_monitor"]["identity_matches"])
        self.assertFalse(result["last_report"]["healthy"])
        self.assertIn("no independent watchdog", result["liveness"])
        self.identity.assert_called_once_with(4242)

    def test_stale_future_naive_invalid_and_missing_heartbeat_never_verify_running(self):
        for stamp, reason in (
            ((NOW - timedelta(seconds=91)).isoformat(), "interval_exceeded"),
            ((NOW + timedelta(seconds=1)).isoformat(), "timestamp_in_future"),
            ("2026-10-23T01:00:00", "timestamp_timezone_missing"),
            ("invalid", "timestamp_invalid"), (None, "timestamp_missing"),
        ):
            with self.subTest(reason=reason):
                self.health(heartbeat_at=stamp)
                self.owner()
                result = self.api.status()
                current = result["current_monitor"]
                self.assertEqual(current["state"], "unknown")
                self.assertEqual(current["heartbeat"]["reason"], reason)
                self.assertEqual(result["last_report"]["state"], "running")
                if reason != "interval_exceeded":
                    self.assertIsNone(result["heartbeat_age_seconds"])

    def test_owner_record_requires_matching_instance_pid_creation_and_namespace(self):
        self.health()
        for changes in ({"pid": 4243}, {"process_created_at": "other"},
                        {"instance_id": "b" * 32}, {"pid": True}, {"instance_id": "invalid"}):
            with self.subTest(changes=changes):
                self.owner(**changes)
                self.identity.reset_mock()
                result = self.api.status()["current_monitor"]
                self.assertEqual(result["state"], "unknown")
                self.identity.assert_not_called()
        self.owner()
        self.health(namespace="unknown")
        self.identity.reset_mock()
        self.assertEqual(self.api.status()["current_monitor"]["reason"], "owner_report_mismatch")
        self.identity.assert_not_called()

    def test_missing_denied_exited_unknown_and_reused_pid_do_not_prove_monitor_running(self):
        self.health()
        self.owner()
        for state, created in (("missing", None), ("exited", CREATED), ("denied", None),
                               ("unknown", None), ("alive", "reused-creation-time")):
            with self.subTest(state=state, created=created):
                self.identity.return_value = {"state": state, "created_at": created}
                current = self.api.status()["current_monitor"]
                self.assertEqual(current["state"], "unknown")
                self.assertFalse(current["identity_matches"])

    def test_stop_request_or_unconfirmed_is_not_running_or_confirmed_exit(self):
        self.owner()
        for state in ("stop_requested", "stopping_pending_query", "shutdown_unconfirmed", "stopped"):
            with self.subTest(state=state):
                self.health(state=state, monitoring=False)
                result = self.api.status()
                self.assertEqual(result["last_report"]["state"], state)
                self.assertEqual(result["current_monitor"]["state"], "unknown")
                self.assertEqual(result["current_monitor"]["reason"], "last_report_not_running")

    def test_coverage_freshness_keeps_denied_partial_and_old_observations_distinct(self):
        self.health(coverage={
            "listeners": {"status": "ok", "observed_at": (NOW - timedelta(seconds=136)).isoformat(),
                          "last_success": (NOW - timedelta(seconds=136)).isoformat()},
            "defender": {"status": "denied", "observed_at": NOW.isoformat()},
            "tasks": {"status": "partial", "observed_at": NOW.isoformat()},
            "services": {"status": "ok", "observed_at": (NOW + timedelta(seconds=1)).isoformat()},
        })
        result = self.api.status()["source_coverage"]
        self.assertEqual(result["listeners"]["status"], "ok")
        self.assertEqual(result["listeners"]["current_coverage"], "unknown")
        self.assertEqual(result["listeners"]["freshness"]["max_age_seconds"], 135)
        self.assertEqual(result["defender"]["current_coverage"], "denied")
        self.assertEqual(result["tasks"]["current_coverage"], "partial")
        self.assertEqual(result["services"]["freshness"]["reason"], "timestamp_in_future")
        self.assertEqual(result["processes"]["current_coverage"], "unknown")

    def test_invalid_config_does_not_promote_saved_ok_coverage(self):
        self.health(coverage={"listeners": {"status": "ok", "observed_at": NOW.isoformat()}})
        (self.root / "config/default.json").write_text("{}", encoding="utf-8")
        value = self.api.status()["source_coverage"]["listeners"]
        self.assertEqual(value["current_coverage"], "unknown")
        self.assertEqual(value["freshness"]["reason"], "freshness_policy_unavailable")

    def test_overview_groups_saved_error_samples_without_changing_status_or_observation(self):
        error = evidence("object", "access_denied", exception_type="Win32Error",
                         win32_error=5, operation="ListenerOpenProcess", status="denied")
        coverage = {"status": "partial", "observed_at": NOW.isoformat(),
                    "errors": [dict(error) for _ in range(64)], "error_count": 170,
                    "errors_truncated": True, "reason": "access_denied",
                    "attempts": [{"backend": "native", "status": "partial", "elapsed_ms": 12,
                                  "errors": [dict(error) for _ in range(64)],
                                  "error_count": 170, "errors_truncated": True}]}
        self.health(coverage={"listeners": coverage})
        self.runtime.save_observation({"id": "listeners", "status": "partial", "rows": [],
            "observed_at": NOW.isoformat(), "coverage": coverage}, "test")
        health_path = self.runtime.path("data/health.json")
        observation_path = self.runtime.path("data/test/observations/listeners.json")
        persisted = health_path.read_bytes(), observation_path.read_bytes()
        before = self.api.status()["source_coverage"]["listeners"]
        observation = self.api.observation("listeners", "test")
        result = self.api.overview("test")["source_coverage"]["listeners"]
        self.assertEqual(result["errors"], [dict(error, sample_occurrences=64)])
        self.assertEqual(result["attempts"][0]["errors"], result["errors"])
        self.assertEqual(result["error_count"], 170)
        self.assertTrue(result["errors_truncated"])
        self.assertEqual({k: v for k, v in result.items() if k not in {"errors", "attempts"}},
                         {k: v for k, v in before.items() if k not in {"errors", "attempts"}})
        self.assertEqual({k: v for k, v in result["attempts"][0].items() if k != "errors"},
                         {k: v for k, v in before["attempts"][0].items() if k != "errors"})
        self.assertEqual(self.api.status()["source_coverage"]["listeners"], before)
        self.assertEqual(self.api.observation("listeners", "test"), observation)
        self.assertEqual((health_path.read_bytes(), observation_path.read_bytes()), persisted)
        size = lambda item: len(json.dumps(item, separators=(",", ":")))
        self.assertLess(size(result), size(before) // 4)

    def test_overview_preserves_distinct_error_codes_and_attempt_order(self):
        base = evidence("object", "access_denied", exception_type="Win32Error",
                        win32_error=5, operation="OpenProcess", status="denied")
        errors = [base, dict(base, win32_error=1314), dict(base, hresult=-2147024891),
                  dict(base, stage="field"), dict(base, exception_type="PermissionError"),
                  dict(base, reason_code="policy_denied"), dict(base, operation="GetProcessTimes")]
        self.health(coverage={"processes": {"status": "partial", "observed_at": NOW.isoformat(),
            "errors": errors * 2, "error_count": 14,
            "attempts": [{"backend": "native", "status": "denied", "errors": [base] * 3},
                         {"backend": "powershell", "status": "unknown", "errors": []}]}})
        result = self.api.overview("test")["source_coverage"]["processes"]
        self.assertEqual(result["errors"], [dict(error, sample_occurrences=2) for error in errors])
        self.assertEqual([(a["backend"], a["status"]) for a in result["attempts"]],
                         [("native", "denied"), ("powershell", "unknown")])
        self.assertEqual(result["attempts"][0]["errors"], [dict(base, sample_occurrences=3)])
        self.assertEqual(result["attempts"][1]["errors"], [])

    def test_overview_error_grouping_never_changes_unknown_denied_or_stale_coverage(self):
        error = evidence("provider", "query_failed", status="unknown")
        coverage = {"defender": {"status": "denied", "observed_at": NOW.isoformat()},
                    "processes": {"status": "unknown", "observed_at": NOW.isoformat()},
                    "tasks": {"status": "partial", "observed_at": (NOW - timedelta(days=1)).isoformat()}}
        for item in coverage.values():
            item["errors"], item["error_count"] = [dict(error)] * 3, 3
        self.health(coverage=coverage)
        before = self.api.status()["source_coverage"]
        after = self.api.overview("test")["source_coverage"]
        for source in before:
            for field in ("status", "current_coverage", "freshness", "observed_at", "last_success"):
                self.assertEqual(after[source][field], before[source][field])
        self.assertEqual(after["defender"]["current_coverage"], "denied")
        self.assertEqual(after["processes"]["current_coverage"], "unknown")
        self.assertEqual(after["tasks"]["current_coverage"], "unknown")
        self.assertEqual(after["listeners"]["current_coverage"], "unknown")

    def test_overview_groups_only_the_requested_namespaces_saved_observation_errors(self):
        error = evidence("provider", "access_denied", win32_error=5, status="denied")
        self.health(coverage={"tasks": {"status": "ok", "observed_at": NOW.isoformat()}})
        self.runtime.save_observation({"id": "tasks", "status": "denied", "rows": [],
            "observed_at": NOW.isoformat(), "coverage": {"errors": [dict(error)] * 4,
                "error_count": 9, "errors_truncated": True}}, "live")
        result = self.api.overview("live")
        tasks = result["source_coverage"]["tasks"]
        self.assertFalse(result["current_monitor"]["scope_matches"])
        self.assertEqual(tasks["status"], "denied")
        self.assertEqual(tasks["current_coverage"], "denied")
        self.assertEqual(tasks["errors"], [dict(error, sample_occurrences=4)])
        self.assertEqual(tasks["error_count"], 9)
        self.assertTrue(tasks["errors_truncated"])
        self.assertEqual(len(self.api.observation("tasks", "live")["coverage"]["errors"]), 4)

    def test_namespace_corruption_is_unknown_without_hiding_other_namespace(self):
        event = make_synthetic()
        store = EventStore(self.root / "data/live")
        store.enqueue(event)
        path = self.root / "data/live/eventguard.sqlite3"
        before = path.read_bytes()
        damaged = self.root / "data/test/eventguard.sqlite3"
        damaged.parent.mkdir()
        damaged.write_bytes(b"not sqlite; private-error-canary")
        result = self.api.status()
        self.assertEqual(result["namespaces"]["live"]["counts"], {"pending": 1})
        self.assertEqual(result["namespaces"]["test"]["state"], "unknown")
        self.assertIsNone(result["namespaces"]["test"]["events"])
        self.assertNotIn("private-error-canary", json.dumps(result))
        self.assertEqual(path.read_bytes(), before)

    def test_status_shows_unfinished_receiver_proofs_without_mutating_or_migrating(self):
        item = make_synthetic()
        store = EventStore(self.root / "data/test")
        store.enqueue(item)
        receipt = {"ack_type": "receiver_persisted", "event_id": item["event_id"], "receipt_id": "synthetic-status-proof"}
        store.acknowledge(item["event_id"], receipt, receiver_finalization=True)
        before = store.path.read_bytes()
        self.assertEqual(self.api.overview("test")["event_storage"]["pending_receiver_finalizations"], 1)
        self.assertEqual(store.path.read_bytes(), before)
        store.finalize_receiver(item["event_id"], receipt)
        self.assertEqual(self.api.status()["namespaces"]["test"]["pending_receiver_finalizations"], 0)
        with closing(sqlite3.connect(store.path)) as db, db:
            db.execute("ALTER TABLE receipts DROP COLUMN pending_finalization")
        before = store.path.read_bytes()
        self.assertIsNone(self.api.status()["namespaces"]["test"]["pending_receiver_finalizations"])
        self.assertEqual(store.path.read_bytes(), before)

    def test_bad_health_and_owner_records_preserve_readable_namespace(self):
        EventStore(self.root / "data/test").enqueue(make_synthetic())
        atomic_json(self.runtime.path("data/monitor-owner.json"), ["invalid"])
        self.runtime.path("data/health.json").write_text("not JSON", encoding="utf-8")
        result = self.api.status()
        self.assertEqual(result["last_report"]["state"], "unknown")
        self.assertEqual(result["current_monitor"]["state"], "unknown")
        self.assertEqual(result["namespaces"]["test"]["counts"]["pending"], 1)
        self.identity.assert_not_called()


class OperatorReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.api = OperatorAPI(self.root)
        self.enterContext(patch("eventguard.operations._owner_identity", side_effect=AssertionError("report queried OS")))
        self.enterContext(patch("eventguard.operations._budget_status", side_effect=AssertionError("report queried budget")))

    def test_empty_report_is_complete_without_creating_an_event_database(self):
        result = self.api.report("test")
        self.assertEqual((result["total"], result["exported"], result["truncated"]), (0, 0, False))
        self.assertFalse((self.root / "data/test/eventguard.sqlite3").exists())

    def test_more_than_1000_fixture_events_report_explicit_truncation_and_escape(self):
        # A persisted legacy/externally populated fixture can exceed today's
        # admission cap; reporting must disclose truncation without admitting it.
        store = EventStore(self.root / "data/test")
        template = make_synthetic()
        template["inference"]["summary"] = "<script>untrusted</script> &"
        rows = []
        for index in range(1001):
            event = copy.deepcopy(template)
            event["event_id"] = "evt-fixture-" + str(index).zfill(4)
            event = validate_event(event)
            rows.append((event["event_id"], json.dumps(event), float(index), float(index), event_payload_hash(event)))
        with closing(sqlite3.connect(store.path)) as db:
            db.executemany("INSERT INTO events(event_id,payload,delivery_status,created_at,updated_at,payload_hash) VALUES(?,?,'pending',?,?,?)", rows)
            db.commit()
        before = store.path.read_bytes()
        result = self.api.report("test")
        document = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
        for value in (result, document):
            self.assertEqual((value["total"], value["exported"], value["truncated"]), (1001, 1000, True))
        self.assertEqual(result["event_count"], 1000)
        self.assertEqual(len(document["events"]), 1000)
        self.assertEqual(document["events"][0]["event_id"], "evt-fixture-1000")
        self.assertTrue(all(event["delivery_status"] == "pending" for event in document["events"]))
        body = Path(result["html"]).read_text(encoding="utf-8")
        self.assertIn("已截斷", body)
        self.assertNotIn("<script>untrusted</script>", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertEqual(store.path.read_bytes(), before)


class BudgetStatusSeamTests(unittest.TestCase):
    def test_budget_status_uses_installation_authority_without_a_runtime_path(self):
        module = ModuleType("eventguard.agent_budget")
        expected = {"state": "blocked", "reason": "budget_fixture_exhausted"}
        with patch.dict(sys.modules, {module.__name__: module}):
            with patch.object(module, "public_status", create=True, return_value=expected) as reader:
                self.assertEqual(_budget_status(object()), expected)
                reader.assert_called_once_with()

    def test_budget_status_failure_is_blocked_without_exception_text(self):
        module = ModuleType("eventguard.agent_budget")
        with patch.dict(sys.modules, {module.__name__: module}):
            with patch.object(module, "public_status", create=True, side_effect=OSError("private path canary")):
                self.assertEqual(_budget_status(object()), {"state": "blocked", "reason": "budget_status_unavailable"})


if __name__ == "__main__":
    unittest.main()
