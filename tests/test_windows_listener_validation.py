"""Pure fixtures: no native collection, child process, socket bind or model."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
SPEC = importlib.util.spec_from_file_location("listener_validation", BASE / "scripts/validate_windows_listener.py")
validation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validation)
from eventguard.rules.detector import evaluate


NOW = datetime(2026, 10, 26, 2, 0, tzinfo=timezone.utc)


def complete_section():
    # Deliberately private-looking fixture facts must never enter saved evidence.
    return {"id": "listeners", "status": "ok", "rows": [{
        "protocol": "TCP", "address": "192.0.2.73", "port": 48291, "pid": 987654,
        "status": "ok", "created_at": "2026-10-25T01:02:03Z",
        "process_instance_ref": "proc-" + "a" * 24, "process_identity_status": "ok",
        "name": "PRIVATE_LISTENER_FIXTURE", "path": "PRIVATE_PATH_FIXTURE"}],
        "coverage": {"status": "ok", "backend": "native", "truncated": False,
                     "errors": [], "error_count": 0, "errors_truncated": False,
                     "process_identity_status": "ok", "process_identity_missing_count": 0,
                     "checks": [{"operation": operation, "status": "ok", "count": 1}
                                for operation in validation.OPERATIONS]}}


class FixtureCollector:
    def __init__(self, section=None, receipt=None, *, pending=False, failure=None):
        self.section = section if section is not None else complete_section()
        receipt = receipt if receipt is not None else {
            "managed": True, "child_exited": True, "exit_code": 0,
            "remaining_owned_processes": 0, "forcibly_terminated": False,
            "pid": 123456, "created_at": "2026-10-25T00:00:00Z",
            "job_name": "PRIVATE_OWN_JOB_FIXTURE"}
        self.runner = Mock(pending=pending, last_process=receipt)
        self.runner.shutdown.return_value = receipt
        self.calls = []
        self.failure = failure

    def collect(self, source, cancel=None):
        self.calls.append(source)
        if self.failure:
            raise self.failure
        return self.section


class ListenerBaselineValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        (self.project / "reports").mkdir()
        for name in validation.SOURCE_FILES:
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture source only\n", encoding="utf-8")
        self.root = self.project / "reports/windows-listener-fixture"

    def prepare(self):
        return validation.prepare(self.root, self.project, now=NOW)

    def approve(self, **updates):
        value = json.loads((self.root / "human-approval.template.json").read_text(encoding="utf-8"))
        value.update(approved=True, approved_at=validation.stamp(NOW),
                     expires_at=validation.stamp(NOW + timedelta(minutes=10)),
                     authorization_text="Fixture approval, no actual native collection.")
        value.update(updates)
        (self.root / "human-approval.json").write_text(json.dumps(value), encoding="utf-8")

    def run_fixture(self, collector, **kwargs):
        return validation.execute(self.root, self.project, now=NOW,
                                  collector_factory=lambda project: collector, **kwargs)

    def test_prepare_is_default_design_and_cannot_grant_itself_approval(self):
        value = self.prepare()
        self.assertEqual(value["status"], "prepared")
        self.assertFalse(value["query_started"])
        self.assertFalse((self.root / "human-approval.json").exists())
        self.assertFalse((self.root / "execution-intent.json").exists())
        manifest = validation._read(self.root / "manifest.json")
        self.assertEqual(manifest["scope"], validation.SCOPE)
        self.assertFalse(manifest["scope"]["socket_bind"])
        self.assertEqual(manifest["scope"]["timeout_sec"], 30)
        self.assertEqual(manifest["loopback_lifecycle"]["reason"], "listener_rule_excludes_loopback")

    def test_missing_approval_has_no_query_or_execution_intent(self):
        self.prepare()
        factory = Mock(side_effect=AssertionError("must not be created"))
        with self.assertRaisesRegex(validation.ValidationError, "approval_missing"):
            validation.execute(self.root, self.project, now=NOW, collector_factory=factory)
        factory.assert_not_called()
        self.assertFalse((self.root / "execution-intent.json").exists())

    def test_existing_stop_request_prevents_collector_and_execution_intent(self):
        self.prepare()
        self.approve()
        (self.root / "stop.request").write_text("", encoding="utf-8")
        factory = Mock(side_effect=AssertionError("must not be created"))
        with self.assertRaisesRegex(validation.ValidationError, "stop_requested_before_query"):
            validation.execute(self.root, self.project, now=NOW, collector_factory=factory)
        factory.assert_not_called()
        self.assertFalse((self.root / "execution-intent.json").exists())

    def test_stop_during_query_cancels_complete_fixture_and_joins_watcher(self):
        self.prepare()
        self.approve()
        collector = FixtureCollector()
        watchers = []
        original_thread = validation.threading.Thread

        def make_thread(*args, **kwargs):
            thread = original_thread(*args, **kwargs)
            watchers.append(thread)
            return thread

        def collect(source, cancel=None):
            self.assertEqual(source, "listeners")
            (self.root / "stop.request").write_text("", encoding="utf-8")
            self.assertTrue(cancel.wait(timeout=2), "stop watcher did not cancel the query")
            return complete_section()  # Even a late complete response must not pass.

        collector.collect = Mock(side_effect=collect)
        with patch.object(validation.threading, "Thread", side_effect=make_thread):
            result = self.run_fixture(collector)
        collector.collect.assert_called_once()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "stop_requested")
        self.assertTrue(result["stop_requested"])
        self.assertTrue(result["stop_watcher_exited"])
        self.assertTrue(result["baseline"]["complete"])
        self.assertEqual(len(watchers), 1)
        self.assertFalse(watchers[0].is_alive())
        self.assertFalse(result["host_safety_assessed"])

    def test_mismatched_expired_and_boolean_scope_all_deny_before_query(self):
        self.prepare()
        cases = [{"approved": False}, {"root": str(self.project)}, {"run_id": "b" * 32},
                 {"manifest_sha256": "0" * 64},
                 {"expires_at": validation.stamp(NOW)},
                 {"approved_at": validation.stamp(NOW - timedelta(seconds=1))},
                 {"expires_at": validation.stamp(NOW + timedelta(minutes=31))},
                 {"scope": dict(validation.SCOPE, source="processes")},
                 {"scope": dict(validation.SCOPE, timeout_sec=31)},
                 {"scope": dict(validation.SCOPE, query_limit=True)},
                 {"scope": dict(validation.SCOPE, socket_bind=True)},
                 {"scope": dict(validation.SCOPE, profile="loopback-lifecycle")}]
        for changes in cases:
            with self.subTest(changes=changes):
                self.approve(**changes)
                factory = Mock()
                with self.assertRaises(validation.ValidationError):
                    validation.execute(self.root, self.project, now=NOW, collector_factory=factory)
                factory.assert_not_called()
                self.assertFalse((self.root / "execution-intent.json").exists())

    def test_changed_source_and_existing_intent_prevent_query(self):
        self.prepare()
        self.approve()
        path = self.project / validation.SOURCE_FILES[0]
        path.write_text("changed\n", encoding="utf-8")
        factory = Mock()
        with self.assertRaisesRegex(validation.ValidationError, "source_changed_since_prepare"):
            validation.execute(self.root, self.project, now=NOW, collector_factory=factory)
        factory.assert_not_called()
        path.write_text("fixture source only\n", encoding="utf-8")
        (self.root / "execution-intent.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            validation.execute(self.root, self.project, now=NOW, collector_factory=factory)
        factory.assert_not_called()

    def test_intent_fsync_failure_prevents_query_and_preserves_no_replay_barrier(self):
        self.prepare()
        self.approve()
        factory = Mock()
        with patch.object(validation.os, "fsync", side_effect=OSError("PRIVATE_FSYNC_FIXTURE")):
            with self.assertRaises(OSError):
                validation.execute(self.root, self.project, now=NOW, collector_factory=factory)
        factory.assert_not_called()
        self.assertTrue((self.root / "execution-intent.json").exists())
        self.assertFalse((self.root / "result.json").exists())
        with self.assertRaises(FileExistsError):
            validation.execute(self.root, self.project, now=NOW, collector_factory=factory)
        factory.assert_not_called()

    def test_dedicated_root_and_fresh_prepare_are_required(self):
        with self.assertRaisesRegex(validation.ValidationError, "dedicated_root_required"):
            validation.prepare(self.project / "data/windows-listener-fixture", self.project, now=NOW)
        self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()

    def test_single_complete_query_natural_job_exit_and_privacy_projection(self):
        self.prepare()
        self.approve()
        collector = FixtureCollector()
        result = self.run_fixture(collector)
        self.assertEqual(collector.calls, ["listeners"])
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["reason"], "baseline_only_verified")
        self.assertFalse(result["full_lifecycle_verified"])
        self.assertFalse(result["host_safety_assessed"])
        self.assertFalse(result["injection_performed"])
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["owned_query"]["pid"], 123456)
        self.assertEqual(result["owned_query"]["created_at"], "2026-10-25T00:00:00.000000+00:00")
        collector.runner.shutdown.assert_not_called()
        saved = (self.root / "result.json").read_text(encoding="utf-8")
        for secret in ("192.0.2.73", "48291", "987654", "PRIVATE_", "process_instance_ref", "2026-10-25T01:02:03"):
            self.assertNotIn(secret, saved)

    def test_denied_partial_truncated_missing_family_or_identity_never_pass(self):
        for index, mutation in enumerate(("denied", "unknown", "timeout", "partial", "truncated",
                                          "missing_family", "identity_gap", "errors")):
            with self.subTest(mutation=mutation):
                section = complete_section()
                if mutation in ("denied", "unknown", "timeout", "partial"):
                    section["status"] = section["coverage"]["status"] = mutation
                elif mutation == "truncated":
                    section["coverage"]["truncated"] = True
                elif mutation == "missing_family":
                    section["coverage"]["checks"].pop()
                elif mutation == "identity_gap":
                    section["coverage"]["process_identity_missing_count"] = 1
                else:
                    section["coverage"]["errors"] = [{"reason_code": "PRIVATE_ERROR_FIXTURE"}]
                self.assertFalse(validation.project_baseline(section)["complete"])
                self.root = self.project / ("reports/windows-listener-incomplete-" + str(index))
                self.prepare()
                self.approve()
                collector = FixtureCollector(section)
                result = self.run_fixture(collector)
                self.assertEqual(result["status"], "blocked")
                self.assertFalse(result["injection_performed"])
                self.assertFalse(result["host_safety_assessed"])
                self.assertEqual(collector.calls, ["listeners"])

    def test_unconfirmed_forced_or_nonzero_job_never_pass(self):
        for index, (field, value) in enumerate((("child_exited", False), ("forcibly_terminated", True),
                                               ("remaining_owned_processes", None), ("remaining_owned_processes", 1),
                                               ("exit_code", 2), ("exit_code", True), ("managed", False),
                                               ("pid", None), ("created_at", None))):
            with self.subTest(field=field, value=value):
                self.root = self.project / ("reports/windows-listener-exit-" + str(index))
                self.prepare()
                self.approve()
                receipt = {"managed": True, "child_exited": True, "exit_code": 0,
                           "pid": 123456, "created_at": "2026-10-25T00:00:00Z",
                           "remaining_owned_processes": 0, "forcibly_terminated": False}
                receipt[field] = value
                result = self.run_fixture(FixtureCollector(receipt=receipt))
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["reason"], "owned_query_exit_unconfirmed")
                self.assertFalse(result["host_safety_assessed"])

    def test_exception_requests_only_injected_owned_runner_cleanup_and_no_raw_error(self):
        self.prepare()
        self.approve()
        collector = FixtureCollector(pending=True, failure=RuntimeError("PRIVATE_EXCEPTION_FIXTURE"))
        result = self.run_fixture(collector)
        collector.runner.shutdown.assert_called_once_with(grace=.2)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "baseline_query_failed")
        self.assertNotIn("PRIVATE_EXCEPTION", json.dumps(result))

    def test_deadline_overrun_is_recorded_as_failure(self):
        self.prepare()
        self.approve()
        result = self.run_fixture(FixtureCollector(), clock=Mock(side_effect=[10.0, 40.1]))
        self.assertEqual(result["reason"], "overall_deadline_exceeded")
        self.assertEqual(result["status"], "blocked")


class LoopbackCapabilityFixtureTests(unittest.TestCase):
    """Confirm the existing product boundary; do not create a new rule or socket."""
    @staticmethod
    def observed(address):
        rows = [] if address is None else [{"protocol": "TCP", "address": address, "port": 18080,
                                            "pid": 42, "status": "ok"}]
        return [{"id": "listeners", "status": "ok", "rows": rows, "coverage": {"status": "ok"}}]

    def test_loopback_is_deliberately_not_a_listener_candidate(self):
        state = None
        for instant in (1000, 1120, 1240):
            state, events = evaluate(self.observed("127.0.0.1"), state, now=instant)
            self.assertFalse([event for event in events if event["event_type"] == "listener.changed"])

    def test_wildcard_fixture_deduplicates_and_needs_two_complete_recovery_rounds(self):
        state, events = evaluate(self.observed("0.0.0.0"), now=1000)
        first = [event for event in events if event["event_type"] == "listener.changed"]
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["transition"], "new")
        for instant in (1120, 1240, 1360):
            state, events = evaluate(self.observed("0.0.0.0"), state, now=instant)
            self.assertFalse([event for event in events if event["event_type"] == "listener.changed"])
        state, events = evaluate(self.observed(None), state, now=1480)
        self.assertFalse([event for event in events if event["event_type"] == "listener.changed"])
        state, events = evaluate(self.observed(None), state, now=1600)
        resolved = [event for event in events if event["event_type"] == "listener.changed"]
        self.assertEqual([event["transition"] for event in resolved], ["resolved"])
        self.assertEqual(resolved[0]["episode_id"], first[0]["episode_id"])


if __name__ == "__main__":
    unittest.main()
