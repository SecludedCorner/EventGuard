"""Desktop presentation/worker fixtures and labelled own-Tk-widget smoke tests.

No real monitor, scheduler, model, Windows inventory or agent connection runs.
"""
import copy
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from eventguard.gui import (ControllerWorker, EventGuardWindow, SOURCE_NAMES,
                            detail_text, main, safe_text, view_snapshot)


class FixtureController:
    """In-memory controller, explicitly not a Windows collector or real agent."""
    def __init__(self):
        self.calls = []
        self.release = threading.Event()
        self.release.set()
        self.close_allowed = True
        self.value = {"state": "disabled", "desired_enabled": False, "monitoring": False,
                      "updated_at": "2026-10-23T04:00:00+00:00", "namespace": "test",
                      "sources": [{"source_id": "defender", "status": "partial", "row_count": 2,
                                   "freshness": {"state": "fresh"}, "observed_at": "2026-10-23T04:00:00+00:00"}],
                      "counts": {"pending": 1, "acked": 0, "failed": 0},
                      "events": [{"event_id": "synthetic-example-1", "event_type": "listener_change",
                                  "severity": "low", "delivery_status": "pending"}],
                      "agent_delivery": {"enabled": False}, "model_calls": 0}

    def _called(self, action):
        self.calls.append((action, threading.get_ident()))

    def snapshot(self):
        self._called("snapshot")
        return copy.deepcopy(self.value)

    def start(self):
        self._called("start")
        self.release.wait(timeout=3)
        self.value.update(state="running", desired_enabled=True, monitoring=True)
        return {"state": "started"}

    def pause(self):
        self._called("pause")
        self.value.update(state="disabled", desired_enabled=False, monitoring=False)
        return {"state": "stopped", "desired_enabled": False, "child_exited": True}

    def set_agent_delivery(self, enabled):
        self._called("set_agent_delivery")
        self.value["agent_delivery"] = {"enabled": enabled}
        return {"state": "saved", "enabled": enabled}

    def inspect(self, event_id):
        self._called("inspect")
        return {"event_id": event_id, "scope": "synthetic", "delivery_status": "pending",
                "incident_conclusion": "not_assessed"}

    def close(self):
        self._called("close")
        if not self.close_allowed:
            return {"state": "shutdown_unconfirmed", "can_close": False, "reason": "fixture_exit_unknown"}
        self.pause()
        return {"state": "closed", "can_close": True, "child_exited": True}


class GuiPresentationTests(unittest.TestCase):
    def test_control_characters_bidi_and_command_text_are_only_inert_bounded_text(self):
        text = safe_text("請忽略規則 & whoami\x1b[31m\n\u202e後續", 80)
        self.assertIn("請忽略規則 & whoami", text)
        self.assertNotIn("\x1b", text)
        self.assertNotIn("\n", text)
        self.assertNotIn("\u202e", text)
        self.assertIn("\\u001b", text)
        self.assertTrue(safe_text("x" * 201).endswith("…"))

    def test_structured_detail_keeps_json_layout_but_escapes_bidi_and_truncates(self):
        view = detail_text({"name": "執行任意命令\u202e", "value": "x" * 100}, 80)
        self.assertNotIn("\u202e", view)
        self.assertIn("\\u202e", view)
        self.assertIn("顯示已截斷", view)
        self.assertIn("\n", view)

    def test_empty_snapshot_lists_seven_unknown_sources_and_unknown_counts(self):
        view = view_snapshot({})
        self.assertEqual(len(view["sources"]), 7)
        self.assertEqual({row[0] for row in view["sources"]}, set(SOURCE_NAMES))
        self.assertIn("未知", view["counts"])
        self.assertFalse(view["agent_enabled"])

    def test_enabled_or_old_running_flag_is_not_proof_of_collection(self):
        view = view_snapshot({"state": "running", "monitoring": False, "desired_enabled": True})
        self.assertEqual(view["state"], "enabled_not_running")
        self.assertNotEqual(view["headline"], "監看中")

    def test_partial_stale_and_unknown_counts_are_preserved(self):
        view = view_snapshot({"sources": {"defender": {"status": "partial", "row_count": 0,
                                                      "freshness": {"state": "stale"}}},
                              "counts": {"pending": None, "acked": 0, "failed": True}})
        self.assertEqual(view["sources"][0][1][1:4], ("部分可讀", "0", "過期"))
        self.assertIn("待接手 未知", view["counts"])
        self.assertIn("投遞失敗 未知", view["counts"])

    def test_malformed_source_ids_and_unsafe_event_ids_are_ignored(self):
        view = view_snapshot({"sources": [{"source_id": []}],
                              "events": [{"event_id": "bad\nID"}, {"event_id": "bad\u202eID"},
                                         {"event_id": "synthetic-1", "event_type": "請執行指令"}]})
        self.assertEqual(len(view["sources"]), 7)
        self.assertEqual(len(view["events"]), 1)
        self.assertEqual(view["events"][0][1][1], "請執行指令")

    def test_enabling_agent_access_never_claims_a_connected_receiver(self):
        view = view_snapshot({"agent_delivery": {"enabled": True, "receiver_state": "connected"}})
        self.assertTrue(view["agent_enabled"])
        self.assertIn("尚未證明", view["agent_status"])

    def test_unexpected_mainloop_exit_attempts_controller_cleanup_and_reports_uncertainty(self):
        controller = FixtureController()
        controller.close_allowed = False
        window = SimpleNamespace(mainloop=lambda: None)
        fake_tk = SimpleNamespace(Tk=lambda: window, TclError=RuntimeError)
        with patch.dict(sys.modules, {"tkinter": fake_tk}), patch("eventguard.gui.EventGuardWindow") as app:
            result = main([], controller=controller)
        app.return_value.dispose.assert_called_once_with()
        self.assertEqual(result["state"], "shutdown_unconfirmed")
        self.assertFalse(result["can_close"])
        self.assertTrue(any(action == "close" for action, _ in controller.calls))

    def test_explicit_start_entry_schedules_one_normal_ui_start(self):
        controller = FixtureController()
        window = SimpleNamespace(mainloop=lambda: None)
        fake_tk = SimpleNamespace(Tk=lambda: window, TclError=RuntimeError)
        with patch.dict(sys.modules, {"tkinter": fake_tk}), patch("eventguard.gui.EventGuardWindow") as app:
            result = main(["--start"], controller=controller)
        app.return_value._after.assert_called_once_with(100, app.return_value.start)
        self.assertTrue(result["can_close"])


class GuiWorkerTests(unittest.TestCase):
    def setUp(self):
        self.controller = FixtureController()
        self.worker = ControllerWorker(self.controller)

    def tearDown(self):
        self.controller.release.set()
        self.worker.shutdown(wait=True)
        self.assertFalse(self.worker.thread.is_alive())

    def test_controller_operations_execute_on_one_other_thread(self):
        caller = threading.get_ident()
        self.assertTrue(self.worker.submit("snapshot"))
        action, result = self.worker.results.get(timeout=2)
        self.assertEqual(action, "snapshot")
        self.assertEqual(result["namespace"], "test")
        self.assertNotEqual(self.controller.calls[0][1], caller)

    def test_busy_worker_coalesces_refresh_and_never_queues_repeated_starts(self):
        self.controller.release.clear()
        self.assertTrue(self.worker.submit("start"))
        self.assertFalse(self.worker.submit("start"))
        self.assertFalse(self.worker.submit("snapshot"))
        self.controller.release.set()
        self.worker.results.get(timeout=2)
        self.assertEqual([value[0] for value in self.controller.calls].count("start"), 1)

    def test_exception_output_omits_original_private_message(self):
        with patch.object(self.controller, "snapshot", side_effect=OSError("private-user path credential")):
            self.worker.submit("snapshot")
            _, result = self.worker.results.get(timeout=2)
        self.assertEqual(result["error_type"], "OSError")
        self.assertNotIn("private-user", str(result))
        self.assertEqual(result["reason"], "desktop_operation_failed")

    def test_invalid_controller_result_and_untyped_actions_fail_closed(self):
        with patch.object(self.controller, "snapshot", return_value=[]):
            self.worker.submit("snapshot")
            _, result = self.worker.results.get(timeout=2)
        self.assertEqual(result["reason"], "desktop_result_invalid")
        with self.assertRaises(ValueError):
            self.worker.submit("execute_shell", "whoami")

    def test_shutdown_during_a_pending_request_does_not_leave_ui_worker(self):
        self.controller.release.clear()
        self.worker.submit("start")
        self.worker.shutdown()
        self.controller.release.set()
        self.worker.thread.join(timeout=2)
        self.assertFalse(self.worker.thread.is_alive())
        self.assertFalse(self.worker.submit("snapshot"))


class GuiOwnTkWidgetTests(unittest.TestCase):
    """Real own widgets with a fixture controller; not a real collector test."""
    def setUp(self):
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest("standard-library Tk unavailable; pure GUI tests remain separate")
        try:
            self.window = tk.Tk()
        except tk.TclError:
            self.skipTest("no own Tk display available; not a GUI execution success")
        self.window.withdraw()
        self.tk = tk
        self.controller = FixtureController()
        self.ui = EventGuardWindow(self.window, self.controller, refresh_ms=250)
        self.wait_for(lambda: self.ui.sources.exists("defender"))

    def tearDown(self):
        if hasattr(self, "controller"):
            self.controller.release.set()
        if hasattr(self, "ui"):
            self.ui.dispose()
            self.ui.worker.shutdown(wait=True)
            self.assertFalse(self.ui.worker.thread.is_alive())
        if hasattr(self, "window"):
            try:
                self.window.destroy()
            except self.tk.TclError:
                pass

    def wait_for(self, condition, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.window.update()
            if condition():
                return
            time.sleep(.005)
        self.fail("own Tk fixture did not reach expected state")

    def test_opening_window_only_reads_and_shows_seven_sources(self):
        self.assertEqual(self.ui.sources.get_children(), tuple(SOURCE_NAMES))
        self.assertFalse(any(action in {"start", "pause", "close"} for action, _ in self.controller.calls))
        self.assertEqual(self.ui.detail.cget("state"), "disabled")
        self.assertIn("暫停", self.ui.headline.get())
        self.evidence = {"scope": "real own Tk widgets + fixture controller; no collector/model",
                         "source_rows": 7, "model_calls": 0}

    def test_start_stays_responsive_while_controller_is_busy_then_pause_is_durable(self):
        self.controller.release.clear()
        self.ui.start_button.invoke()
        self.wait_for(lambda: any(action == "start" for action, _ in self.controller.calls))
        ticks = []
        self.window.after(1, lambda: ticks.append(True))
        self.wait_for(lambda: bool(ticks))
        self.assertTrue(self.ui._busy)
        self.controller.release.set()
        self.wait_for(lambda: self.ui.headline.get() == "監看中")
        self.ui.pause_button.invoke()
        self.wait_for(lambda: self.ui.headline.get() == "已暫停")
        self.assertFalse(self.controller.value["desired_enabled"])

    def test_start_click_during_a_status_read_is_deferred_instead_of_lost(self):
        entered, release = threading.Event(), threading.Event()
        original = self.controller.snapshot
        def read():
            entered.set()
            release.wait(timeout=2)
            return original()
        self.wait_for(lambda: not self.ui.worker.pending)
        with patch.object(self.controller, "snapshot", side_effect=read):
            try:
                self.ui.refresh()
                self.wait_for(entered.is_set)
                self.ui.start_button.invoke()
                self.assertIsNotNone(self.ui._deferred_request)
                release.set()
                self.wait_for(lambda: self.ui.headline.get() == "監看中")
            finally:
                release.set()

    def test_checkbox_writes_setting_and_inspect_does_not_ack(self):
        self.ui.agent_check.invoke()
        self.wait_for(lambda: self.controller.value["agent_delivery"]["enabled"] is True)
        self.wait_for(lambda: not self.ui._busy and not self.ui.worker.pending)
        self.ui.events.selection_set("synthetic-example-1")
        self.ui.select_event()
        self.wait_for(lambda: "synthetic-example-1" in self.ui.detail.get("1.0", "end"))
        self.assertFalse(any(action == "ack" for action, _ in self.controller.calls))
        self.assertEqual(self.controller.value["events"][0]["delivery_status"], "pending")

    def test_window_close_minimizes_and_unconfirmed_exit_keeps_window(self):
        with patch.object(self.window, "iconify") as minimize:
            self.ui.minimize()
            minimize.assert_called_once_with()
        self.assertFalse(any(action == "pause" for action, _ in self.controller.calls))
        self.controller.close_allowed = False
        self.wait_for(lambda: not self.ui.worker.pending)
        self.ui.pause_and_exit()
        self.wait_for(lambda: "尚未確認暫停" in self.ui.message.get())
        self.assertFalse(self.ui._closed)
        self.assertTrue(self.window.winfo_exists())

