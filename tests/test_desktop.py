"""Desktop application controller fixtures; no real GUI, collector or model."""
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from eventguard import desktop


class DesktopTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
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

    def test_journal_failure_cannot_block_revoking_agent_access(self):
        from eventguard.activity import ActivityError
        for method, setting in ((self.controller.set_agent_delivery, "eventguard.agent_access.set_enabled"),
                                (self.controller.set_automatic_agent, "eventguard.agent_automation.set_enabled")):
            for keyword in (False, True):
                with self.subTest(method=method.__name__, keyword=keyword), \
                        patch("eventguard.activity.begin", side_effect=ActivityError("activity_storage_unavailable")), \
                        patch(setting, return_value={"status": "disabled", "setting_saved": True}) as change:
                    result = method(enabled=False) if keyword else method(False)
                    change.assert_called_once_with(self.root, False)
                    self.assertEqual(result["activity_warning"], "activity_storage_unavailable")
                    change.reset_mock()
                    blocked = method(enabled=True) if keyword else method(True)
                    change.assert_not_called()
                    self.assertFalse(blocked["operation_started"])

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
        # The overview still owns event counts; saved source evidence owns the
        # source row, including its reasons and historical collection result.
        source_row = {"source_id": "listeners", "status": "stale", "saved_status": "partial", "row_count": 8,
            "last_collected_at": "2026-10-23T00:00:00+00:00", "freshness": "stale",
            "last_success_at": None, "last_success_state": "unknown",
            "reasons": self.controller.api.call.return_value["source_coverage"]["listeners"]["errors"]}
        from eventguard.source_status import source_status
        saved = source_status(self.root, "live")
        saved['sources'] = [source_row if row['source_id'] == 'listeners' else row for row in saved['sources']]
        with patch('eventguard.source_status.source_status', return_value=saved):
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
        with patch("eventguard.events.catalog.EventCatalog") as catalog:
            catalog.return_value.detail.return_value = {"event_id": "event-1", "investigation": None}
            value = self.controller.inspect("event-1")
            catalog.assert_called_once_with(self.root, "live")
            catalog.return_value.detail.assert_called_once_with("event-1")
        self.controller.api.call.assert_not_called()
        self.assertFalse(value["system_query_executed"])

    def test_inspect_reads_saved_case_without_changing_events_or_ack(self):
        import hashlib
        from eventguard.events.catalog import EventCatalog
        from eventguard.events.store import EventStore
        from eventguard.synthetic import make_synthetic
        event = make_synthetic()
        directory = self.root / 'data/live'
        store = EventStore(directory)
        store.enqueue(event)
        catalog = EventCatalog(self.root, 'live')
        catalog.investigate(event['event_id'])
        path = directory / 'eventguard.sqlite3'
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        with patch('eventguard.collectors.windows.WindowsCollectors.collect', side_effect=AssertionError('no scan')):
            value = self.controller.inspect(event['event_id'])
        self.assertIsInstance(value['investigation'], dict)
        self.assertIsInstance(value['investigation_revisions'], dict)
        self.assertIn('handling_history', value)
        self.assertEqual(value['event']['delivery_status'], 'pending')
        self.assertFalse(value['system_query_executed'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
        self.controller.api.call.assert_not_called()

    def test_snapshot_preserves_saved_success_after_denial_without_collecting(self):
        import hashlib
        import shutil
        from eventguard.runtime import Runtime
        (self.root/'config').mkdir()
        shutil.copyfile(Path(__file__).resolve().parents[1]/'config/default.json', self.root/'config/default.json')
        runtime = Runtime(self.root)
        for status, at in (("ok", "2026-01-01T00:00:00+00:00"), ("denied", "2026-01-02T00:00:00+00:00")):
            runtime.save_observation({"id": "defender", "status": status, "observed_at": at,
                                      "coverage": {"status": status, "errors": []}, "rows": []}, "live")
        self.controller.api.call.return_value = {
            "source_coverage": {"defender": {"status": "denied", "freshness": {"state": "stale"}}}}
        def hashes():
            return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in self.root.rglob('*') if p.is_file()}
        before = hashes()
        with patch("eventguard.collectors.windows.WindowsCollectors.collect", side_effect=AssertionError("no scan")):
            value = self.controller.snapshot()
        source = value["sources"][0]
        self.assertEqual(source["status"], "denied")
        self.assertEqual(source["freshness"]["state"], "stale")
        self.assertEqual(source["last_success_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(source["last_success_state"], "known")
        self.assertEqual(value["sources"][1]["last_success_state"], "unknown")
        self.assertEqual(before, hashes())
        self.controller.api.call.assert_called_once_with("overview", namespace="live", limit=100)

    def test_event_snapshot_exposes_total_and_loaded_window_without_new_query(self):
        self.controller.api.call.return_value = {
            "event_list": {"events": [{"event_id":"synthetic-1"}], "total":487, "truncated":True},
            "event_storage": {"state":"available","counts":{"pending":487}}}
        value=self.controller.snapshot()
        self.assertEqual(value["events_total"],487)
        self.assertEqual(value["events_limit"],100)
        self.assertTrue(value["events_truncated"])
        self.assertEqual(len(value["events"]),1)
        self.controller.api.call.assert_called_once_with("overview",namespace="live",limit=100)
        self.controller.api.call.reset_mock()
        self.controller.api.call.return_value["event_list"]["total"]=True
        self.assertIsNone(self.controller.snapshot()["events_total"])

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


class DesktopAutomaticAgentTests(unittest.TestCase):
    """Fake dispatcher only; proves control ownership without any model calls."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.executable = self.root / "codex.exe"
        self.executable.write_bytes(b"inert fixture, never execute")
        self.controller = desktop.DesktopController(self.root)
        self.controller.api = Mock(return_value={})
        self.entered = threading.Event()
        self.cancel = None
        self.invocations = []
        self.final = {"state": "waiting", "child_exited": True, "tasks_started": 0}
        self.enterContext(patch("eventguard.agent_access.guard", return_value=None))
        self.enterContext(patch("eventguard.agent_dispatch.run", side_effect=self.dispatch))
        self.status_mock = self.enterContext(patch("eventguard.agent_dispatch.status",
            side_effect=lambda _, **kwargs: dict(self.final)))
        self.addCleanup(self.cleanup_worker)

    def dispatch(self, directory, **kwargs):
        self.invocations.append((directory, kwargs))
        self.cancel = kwargs["cancel"]
        self.entered.set()
        self.cancel.wait(timeout=3)
        self.final.update(state="stopped", child_exited=True)
        return 0

    def cleanup_worker(self):
        self.controller._agent_cancel.set()
        worker = self.controller._agent_thread
        if worker is not None:
            worker.join(timeout=4)
            self.assertFalse(worker.is_alive(), "fake dispatcher must not survive test teardown")

    def test_reading_saved_opt_in_never_starts_dispatcher(self):
        from eventguard.agent_automation import set_enabled
        set_enabled(self.root, True, str(self.executable))
        view = self.controller._automatic_snapshot()
        self.assertTrue(view["enabled"])
        self.assertEqual(view["state"], "armed")
        self.assertEqual(self.invocations, [])

    def test_finished_worker_mcp_summary_is_refreshed_readonly_instead_of_using_cache(self):
        self.controller._agent_run_dir = self.root / "reports" / "fixture-agent"
        self.controller._agent_result = {"state": "stopped", "mcp_lifecycle": {
            "status": "verified", "exit_code": 0, "ack_flushed": True, "reason": "mcp_natural_exit_verified"}}
        self.final = {"state": "stopped", "mcp_lifecycle": {
            "status": "unknown", "exit_code": None, "ack_flushed": None, "reason": "mcp_lifecycle_evidence_unverified"}}
        value = self.controller._automatic_snapshot()
        self.assertEqual(value["mcp_lifecycle"]["status"], "unknown")
        self.assertFalse(value["worker_alive"])
        self.status_mock.assert_called_once_with(self.controller._agent_run_dir, read_only=True)
        self.assertEqual(self.invocations, [])

    def test_opt_in_while_paused_only_saves_until_explicit_start(self):
        with patch.object(desktop.background, "status", return_value={"state": "stopped"}):
            result = self.controller.set_automatic_agent(True, str(self.executable))
        self.assertEqual(result["state"], "armed")
        self.assertEqual(self.invocations, [])
        with (patch.object(desktop.background, "status", return_value={"state": "stopped"}),
              patch.object(desktop.background, "start", return_value={"state": "started"})):
            self.controller.start()
        self.assertTrue(self.entered.wait(timeout=2))
        directory, args = self.invocations[0]
        self.assertEqual(args["source_dir"], self.root / "data/live")
        self.assertEqual(args["state_dir"], self.root / "data/agent-delivery")
        self.assertTrue(args["continuous"])
        self.assertTrue(args["execute"])
        self.assertTrue(args["allow_live"])
        self.assertEqual(directory.parent, self.root / "reports/automatic-agent")

    def test_live_monitor_click_starts_one_worker_and_disable_joins_it(self):
        with patch.object(desktop.background, "status", return_value={"state": "running"}):
            self.controller.set_automatic_agent(True, str(self.executable))
            self.assertTrue(self.entered.wait(timeout=2))
            self.controller.set_automatic_agent(True, str(self.executable))
        self.assertEqual(len(self.invocations), 1)
        result = self.controller.set_automatic_agent(False)
        self.assertTrue(result["child_exited"])
        self.assertTrue(self.cancel.is_set())
        self.assertIsNone(self.controller._agent_thread)

    def test_pause_stops_worker_but_preserves_explicit_saved_choice(self):
        from eventguard.agent_automation import status
        with patch.object(desktop.background, "status", return_value={"state": "running"}):
            self.controller.set_automatic_agent(True, str(self.executable))
        self.assertTrue(self.entered.wait(timeout=2))
        with (patch.object(desktop.background, "status", return_value={"state": "running"}),
              patch.object(desktop.background, "stop", return_value=DesktopTests.stopped())):
            result = self.controller.pause()
        self.assertTrue(result["can_close"])
        self.assertTrue(result["automatic_agent_exited"])
        self.assertTrue(status(self.root)["enabled"])
        self.assertEqual(self.controller._automatic_snapshot()["state"], "armed")

    def test_receive_gate_is_required_separately(self):
        with patch("eventguard.agent_access.guard", return_value={"status": "blocked"}):
            result = self.controller.set_automatic_agent(True, str(self.executable))
        self.assertEqual(result["reason"], "agent_receive_permission_required")
        self.assertEqual(self.invocations, [])

    def test_missing_exe_does_not_start_or_save_enabled(self):
        from eventguard.agent_automation import status
        result = self.controller.set_automatic_agent(True, str(self.root / "missing.exe"))
        self.assertEqual(result["state"], "blocked")
        self.assertFalse(status(self.root)["enabled"])
        self.assertEqual(self.invocations, [])

    def test_unconfirmed_worker_exit_keeps_application_open(self):
        self.controller._agent_thread = Mock()
        self.controller._agent_thread.is_alive.return_value = True
        with (patch.object(desktop.background, "status", return_value={"state": "running"}),
              patch.object(desktop.background, "stop", return_value=DesktopTests.stopped())):
            result = self.controller.close()
        self.assertFalse(result["can_close"])
        self.assertEqual(result["state"], "shutdown_unconfirmed")
        self.assertFalse(self.controller._closed)
        self.controller._agent_thread = None

    def test_finished_worker_without_child_exit_proof_is_not_assumed_stopped(self):
        self.controller._agent_thread = Mock()
        self.controller._agent_thread.is_alive.return_value = False
        self.controller._agent_result = {"state": "unknown"}
        self.assertFalse(self.controller._stop_automatic_agent())
        self.controller._agent_thread = None
