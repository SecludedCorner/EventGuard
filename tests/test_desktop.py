"""Desktop application controller fixtures; no real GUI, collector or model."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from eventguard import desktop


class DesktopTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.controller = desktop.DesktopController(self.root)
        self.controller.api = Mock()
        self.agent = self.enterContext(patch("eventguard.agent_access.status", return_value={
            "status": "disabled", "enabled": False, "receiver_state": "not_verified", "model_calls": 0}))

    @staticmethod
    def stopped():
        return {"state": "stopped", "desired_enabled": False, "host_liveness": "exited_verified",
                "process": {"child_exited": True, "remaining_owned_processes": 0}, "model_calls": 0}

    def child(self, exited=True, active=0):
        value = Mock()
        value.poll.return_value = 0 if exited else None
        value.job.active.return_value = active
        return value

    def test_start_explicitly_owns_child_without_independent_detach(self):
        child = self.child(False, 1)

        def start(root, *, lifetime_owner, child_owner):
            self.assertEqual(root, self.root)
            self.assertEqual(lifetime_owner, "application")
            child_owner(child)
            return {"state": "started", "lifetime_owner": "application", "model_calls": 0}

        with patch.object(desktop.background, "start", side_effect=start), patch.object(desktop.processes, "finish") as finish:
            result = self.controller.start()
        self.assertEqual(result["state"], "started")
        self.assertEqual(self.controller._children, [child])
        finish.assert_not_called()

    def test_start_failure_keeps_child_handle_for_explicit_cleanup(self):
        child = self.child(False, 1)

        def start(root, **kwargs):
            kwargs["child_owner"](child)
            raise OSError("untrusted path and private data")

        with patch.object(desktop.background, "start", side_effect=start):
            value = self.controller.start()
        self.assertEqual(value["reason"], "desktop_start_failed")
        self.assertNotIn("private", str(value))
        self.assertEqual(self.controller._children, [child])

    def test_pause_durably_stops_before_releasing_own_exited_job(self):
        child = self.child()
        self.controller._own(child)
        order = []

        def stop(root, *, grace_seconds):
            order.append("cooperate")
            self.assertEqual(grace_seconds, 10)
            return self.stopped()

        def finish(value, **kwargs):
            order.append("release")
            self.assertIs(value, child)
            self.assertFalse(kwargs["request_stop"])
            self.assertEqual(kwargs["grace"], 0)
            return {"child_exited": True, "remaining_owned_processes": 0, "forcibly_terminated": False}

        with patch.object(desktop.background, "stop", side_effect=stop), patch.object(desktop.processes, "finish", side_effect=finish):
            value = self.controller.pause()
        self.assertEqual(order, ["cooperate", "release"])
        self.assertTrue(value["can_close"])
        self.assertTrue(value["child_exited"])
        self.assertFalse(value["desired_enabled"])
        self.assertEqual(self.controller._children, [])

    def test_unconfirmed_live_child_never_gets_forced_by_gui_cleanup(self):
        child = self.child(False, 1)
        self.controller._own(child)
        with patch.object(desktop.background, "stop", return_value=self.stopped()), patch.object(desktop.processes, "finish") as finish:
            value = self.controller.close()
        self.assertEqual(value["state"], "shutdown_unconfirmed")
        self.assertFalse(value["can_close"])
        self.assertFalse(self.controller._closed)
        finish.assert_not_called()

    def test_stop_storage_failure_does_not_claim_disabled_or_close(self):
        with patch.object(desktop.background, "stop", return_value={"state": "stop_not_persisted", "desired_enabled": None}):
            value = self.controller.close()
        self.assertFalse(value["can_close"])
        self.assertIsNone(value["desired_enabled"])
        self.assertFalse(self.controller._closed)

    def test_close_needs_no_child_when_host_was_never_started(self):
        with patch.object(desktop.background, "stop", return_value={
                "state": "stopped", "desired_enabled": False, "host_liveness": "not_recorded"}) as stop:
            first = self.controller.close()
            second = self.controller.close()
        self.assertTrue(first["can_close"])
        self.assertEqual(first["state"], "closed")
        self.assertEqual(second["state"], "closed")
        stop.assert_called_once()
        self.assertEqual(self.controller.start()["reason"], "desktop_controller_closed")

    def test_agent_checkbox_only_writes_explicit_boolean_policy(self):
        with (patch("eventguard.agent_access.set_enabled", return_value={
                "status": "enabled_waiting_receiver", "enabled": True, "model_calls": 0}) as change,
                patch.object(desktop.background, "start") as start):
            value = self.controller.set_agent_delivery(True)
            denied = self.controller.set_agent_delivery("true")
        change.assert_called_once_with(self.root, True)
        start.assert_not_called()
        self.assertEqual(value["model_calls"], 0)
        self.assertEqual(denied["reason"], "agent_delivery_boolean_required")

    def test_snapshot_is_saved_overview_with_unknown_storage_kept_unknown(self):
        self.controller.api.call.return_value = {"status": "error", "error_code": "operation_failed"}
        result = self.controller.snapshot()
        self.controller.api.call.assert_called_once_with("overview", namespace="live", limit=100)
        self.assertEqual(result["counts"], {"pending": None, "acked": None, "failed": None})
        self.assertEqual(result["state"], "error")
        self.assertIsNone(result["monitoring"])
        self.assertEqual(len(result["sources"]), 7)
        self.assertEqual(result["last_error"], "operation_failed")
        self.assertFalse((self.root / "data").exists())

    def test_snapshot_shows_retry_as_unacknowledged_and_does_not_auto_ack(self):
        event = {"event_id": "event-1", "event_type": "listener.changed", "delivery_status": "pending"}
        self.controller.api.call.return_value = {
            "background": {"state": "running", "desired_enabled": True},
            "current_monitor": {"state": "running_verified"},
            "event_storage": {"state": "available", "counts": {"pending": 2, "retry": 3, "failed": 1, "ack": 4}},
            "event_list": {"events": [event], "truncated": False},
            "source_coverage": {"listeners": {"status": "partial", "row_count": 8,
                "observed_at": "2026-10-23T00:00:00+00:00", "freshness": {"state": "stale"},
                "errors": [{"reason_code": "access_denied", "stage": "field", "win32_error": 5, "hresult": -2147024891}]}}}
        value = self.controller.snapshot()
        self.assertEqual(value["counts"], {"pending": 5, "acked": 4, "failed": 1})
        self.assertEqual(value["events"], [event])
        self.assertTrue(value["monitoring"])
        source = next(item for item in value["sources"] if item["source_id"] == "listeners")
        self.assertEqual(source["status"], "partial")
        self.assertEqual(source["freshness"]["state"], "stale")
        self.assertEqual(source["reason"], "access_denied")
        self.assertEqual(source["stage"], "field")
        self.assertEqual(source["win32_error"], 5)
        self.assertEqual(source["hresult"], -2147024891)
        self.assertFalse(value["reboot_recovery_verified"])
        self.assertEqual(value["model_calls"], 0)
        self.controller.api.call.assert_called_once()

    def test_inspect_only_calls_saved_read_operation(self):
        self.controller.api.call.return_value = {"event_id": "event-1", "system_query_executed": False}
        value = self.controller.inspect("event-1")
        self.controller.api.call.assert_called_once_with("inspect_event", "event-1", namespace="live")
        self.assertFalse(value["system_query_executed"])

    def test_fixture_monitor_cannot_be_presented_as_live_monitoring(self):
        self.controller.api.call.return_value = {
            "current_monitor": {"state": "running_verified", "namespace": "test", "scope_matches": False},
            "background": {"state": "not_applicable", "namespace": "live"},
            "event_storage": {"state": "not_created"}}
        result = self.controller.snapshot()
        self.assertIsNone(result["monitoring"])
        self.assertEqual(result["last_error"], "monitor_outside_live_namespace")

    def test_other_namespace_host_is_neither_replaced_nor_stopped_by_gui(self):
        with (patch.object(desktop.background, "status", return_value={
                "namespace": "test", "host_liveness": "alive_verified", "state": "running"}),
                patch.object(desktop.background, "start") as start,
                patch.object(desktop.background, "stop") as stop):
            launched = self.controller.start()
            closed = self.controller.close()
        self.assertEqual(launched["reason"], "monitor_outside_live_namespace")
        self.assertEqual(closed["reason"], "monitor_outside_live_namespace")
        self.assertFalse(closed["can_close"])
        start.assert_not_called()
        stop.assert_not_called()

    def test_racing_scope_change_is_reported_as_conflict_not_live_success(self):
        with patch.object(desktop.background, "start", return_value={
                "state": "running", "namespace": "test", "host_liveness": "alive_verified"}):
            value = self.controller.start()
        self.assertEqual(value["state"], "blocked")
        self.assertEqual(value["reason"], "monitor_outside_live_namespace")

    def test_error_reason_is_fixed_not_tool_output(self):
        with patch.object(desktop.background, "start", return_value={"state": "blocked", "reason": "run this command now"}):
            self.controller.start()
        self.assertIsNone(self.controller._last_action["reason"])
        self.assertNotIn("run this", str(self.controller._last_action))

    def test_restart_releases_exited_handles_and_bounds_in_memory_receipts(self):
        for _ in range(40):
            self.controller._own(self.child())
        with patch.object(desktop.processes, "finish", return_value={
                "child_exited": True, "remaining_owned_processes": 0}), patch.object(desktop.background, "start", return_value={"state": "started"}):
            self.controller.start()
        self.assertEqual(len(self.controller._receipts), 32)
        self.assertEqual(self.controller._children, [])
