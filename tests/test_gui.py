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
                      "events": [{"event_id": "synthetic-example-1", "event_type": "listener.changed",
                                  "observed_at": "2026-10-23T04:00:00+00:00",
                                  "severity": "warning", "delivery_status": "pending"}],
                      "events_total": 1, "events_truncated": False,
                      "agent_delivery": {"enabled": False}, "model_calls": 0}
        self.value["automatic_agent"] = {"enabled": False, "state": "disabled"}

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

    def set_automatic_agent(self, enabled, executable=None):
        self._called("set_automatic_agent")
        self.value["automatic_agent"] = {"enabled": enabled, "state": "waiting" if enabled else "disabled"}
        return {"state": "waiting" if enabled else "disabled", "enabled": enabled}

    def inspect(self, event_id):
        self._called("inspect")
        event = next(item for item in self.value["events"] if item["event_id"] == event_id)
        return {"event": copy.deepcopy(event), "scope": "synthetic", "incident_conclusion": "not_assessed",
                "guidance": {"observation": "保存的合成監聽觀察，不代表外部可達或惡意。",
                             "binding_facts": {"protocol": "TCP", "port": 43210},
                             "next_steps": ["核對保存的 port 與綁定範圍。"],
                             "uncertainties": ["process_binding_missing"]}}

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
        self.assertIn("未知／尚無觀察 7", view["source_gaps"])

    def test_source_gaps_count_overlap_without_promoting_history_to_current_success(self):
        rows = [{"source_id": key, "status": state, "freshness": {"state": fresh},
                 "last_success_state": "known", "last_success_at": "2026-01-01T00:00:00Z"}
                for key, (state, fresh) in zip(SOURCE_NAMES, [("denied", "stale"), ("partial", "fresh"),
                    ("error", "fresh"), ("ok", "fresh"), ("ok", "unknown"), ("not_applicable", "fresh"), ([], [])])]
        view = view_snapshot({"sources": rows})
        for text in ("可讀且新鮮 1", "拒讀 1", "部分可讀 1", "讀取失敗 1", "過期 1", "未知／尚無觀察 2", "不適用 1", "非安全判定"):
            self.assertIn(text, view["source_gaps"])

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
        self.assertFalse(view["automatic_enabled"])

    def test_automatic_wait_attention_and_historical_states_are_honest_without_quota(self):
        # No daily quota. A saved historical budget wait only asks for a recheck.
        for state, message in (("waiting", "無事件不呼叫模型"), ("waiting_budget", "舊派送狀態需重新核對"),
                               ("waiting_attention", "不自動重試"), ("waiting_task_limit", "本次執行已達任務上限"),
                               ("armed", "按開始")):
            view = view_snapshot({"automatic_agent": {"enabled": True, "state": state}})
            self.assertTrue(view["automatic_enabled"])
            self.assertFalse(view["agent_enabled"])
            self.assertIn(message, view["automatic_status"])
            self.assertNotIn("每日", view["automatic_status"])
            self.assertIn("有效的明確授權", view["automatic_status"])
            self.assertIn("不接續本聊天", view["automatic_status"])

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
        self.assertIn("部分可讀 1", self.ui.source_gaps.get())
        self.assertIn("未知／尚無觀察 6", self.ui.source_gaps.get())
        self.evidence = {"scope": "real own Tk widgets + fixture controller; no collector/model",
                         "source_rows": 7, "model_calls": 0}

    def test_real_detail_widget_displays_saved_case_and_replaces_it_with_unknown(self):
        event = copy.deepcopy(self.controller.value["events"][0])
        document = {"event": event, "investigation": {"case": {
            "anchor_event_id": event["event_id"], "case_id": "case-fixture", "status": "limited",
            "as_of": "2026-01-01T00:00:00Z", "timeline": [{}], "gaps": [{}]},
            "evidence_status": "unknown", "snapshot_freshness": "stale", "diagnostic_evidence_status": "missing"}}
        self.ui._show_detail(document)
        self.window.update_idletasks()
        text = self.ui.detail.get('1.0', 'end')
        for expected in ("case-fixture", "成員證據：未知", "診斷缺失", "快照新鮮度：過期"):
            self.assertIn(expected, text)
        self.assertEqual(self.ui.detail.cget('state'), 'disabled')
        self.ui._show_detail({"event": event, "investigation": None})
        text = self.ui.detail.get('1.0', 'end')
        self.assertIn('尚未保存調查', text)
        self.assertNotIn('case-fixture', text)
        self.assertFalse(any(action != 'snapshot' for action, _ in self.controller.calls))

    def test_operation_history_tab_shows_agent_progress_and_completion(self):
        row = {"id": "a" * 32, "actor": "agent_mcp", "operation": "diagnose_event", "state": "running",
               "started_at": "2026-10-23T08:00:00+00:00", "elapsed_ms": None}
        self.controller.value["activity"] = {"state": "available", "entries": [row], "active": 1, "total": 1}
        self.ui._apply_snapshot(copy.deepcopy(self.controller.value))
        self.assertEqual(self.ui.activities.item(row["id"], "values")[1:4], ("Agent 工具", "唯讀查證", "執行中／待結果"))
        row.update(state="completed", elapsed_ms=25, result_code="reviewed")
        self.controller.value["activity"]["active"] = 0
        self.ui._apply_snapshot(copy.deepcopy(self.controller.value))
        self.assertEqual(self.ui.activities.item(row["id"], "values")[3], "已完成")
        self.assertIn("執行中 0", self.ui.activity_status.get())

    def test_real_detail_widget_renders_catalog_saved_timeline_without_creating_new_work(self):
        import tempfile
        from pathlib import Path
        from eventguard.events.catalog import EventCatalog
        from eventguard.events.store import EventStore
        from eventguard.synthetic import make_synthetic
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            event = make_synthetic()
            EventStore(root/'data/test').enqueue(event)
            catalog = EventCatalog(root, 'test')
            catalog.investigate(event['event_id'])
            document = catalog.detail(event['event_id'])
            self.ui._show_detail(document)
            self.window.update_idletasks()
            text = self.ui.detail.get('1.0', 'end')
            self.assertIn(event['event_id'], text)
            self.assertIn('保存時間線（最多16項', text)
            self.assertIn('非因果鏈', text)
            self.assertIn('與保存雜湊相符', text)
            self.assertEqual(self.ui.detail.cget('state'), 'disabled')
            self.assertEqual(catalog.detail(event['event_id'])['event']['delivery_status'], 'pending')
        self.assertFalse(any(action != 'snapshot' for action, _ in self.controller.calls))

    def test_real_detail_widget_renders_actual_saved_case_revision_and_clears_unknown(self):
        import tempfile
        from pathlib import Path
        from datetime import datetime, timedelta
        from eventguard.events.catalog import EventCatalog
        from eventguard.events.store import EventStore
        from eventguard.synthetic import make_synthetic
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            event = make_synthetic()
            EventStore(root/'data/test').enqueue(event)
            catalog = EventCatalog(root, 'test')
            catalog.investigate(event['event_id'], now=event['observed_at'])
            catalog.investigate(event['event_id'], now=(datetime.fromisoformat(event['observed_at']) + timedelta(seconds=1)).isoformat())
            document = catalog.detail(event['event_id'])
            self.ui._show_detail(document)
            text = self.ui.detail.get('1.0', 'end')
            self.assertIn('保存前版 1', text)
            self.assertIn('保存成員相符', text)
            self.ui._show_detail({'event': document['event'], 'investigation_revisions': {'state': 'unknown'}})
            text = self.ui.detail.get('1.0', 'end')
            self.assertIn('前版調查歷程未知', text)
            self.assertNotIn('前版保存時間：', text)
            self.assertEqual(catalog.detail(event['event_id'])['event']['delivery_status'], 'pending')
        self.assertFalse(any(action != 'snapshot' for action, _ in self.controller.calls))

    def test_real_detail_widget_shows_handled_while_delivery_remains_pending(self):
        document = {"event": copy.deepcopy(self.controller.value["events"][0]), "status": "handled",
                    "handling_history": {"state": "available", "count_capacity": "available", "entries": [
                        {"previous_status": "new", "status": "handled", "source": "gui",
                         "at": "2026-01-01T00:00:00Z", "changed": True}]}}
        self.ui._show_detail(document)
        self.window.update_idletasks()
        text = self.ui.detail.get('1.0', 'end')
        for expected in ('人工處置狀態：已處理', '接收狀態：待接手', '新增 → 已處理', '這不是投遞 ACK'):
            self.assertIn(expected, text)
        self.ui._show_detail({"event": document["event"], "handling_history": {"state": "unknown"}})
        text = self.ui.detail.get('1.0', 'end')
        self.assertIn('處置歷程未知', text)
        self.assertNotIn('新增 → 已處理', text)
        self.assertEqual(self.ui.detail.cget('state'), 'disabled')
        self.assertFalse(any(action != 'snapshot' for action, _ in self.controller.calls))

    def test_real_source_widgets_separate_history_from_denial_staleness_and_missing(self):
        at = "2026-01-01T00:00:00+00:00"
        document = copy.deepcopy(self.controller.value)
        cases = [("denied", "fresh", "known", at), ("ok", "stale", "known", at),
                 ("unknown", "unknown", "unknown", None), ("denied", "fresh", "known", "invalid"),
                 ("ok", "fresh", "known", "9999-01-01T00:00:00Z"), ("ok", "fresh", "known", at)]
        before = copy.deepcopy(document)
        for source, (status, fresh, known, success) in zip(SOURCE_NAMES, cases):
            document["sources"] = [{"source_id": source, "status": status, "row_count": 0,
                                   "freshness": {"state": fresh}, "last_success_state": known,
                                   "last_success_at": success}]
            self.ui._apply_snapshot(document)
            self.window.update_idletasks()
            row = self.ui.sources.item(source, "values")
            self.assertEqual(row[2], "0")
            self.assertEqual(row[5], at if known == "known" and success == at else "未知／尚無成功紀錄")
            if status == "denied":
                self.assertEqual(row[1], "拒讀")
            if fresh == "stale":
                self.assertEqual(row[3], "過期")
                self.assertIn("過期 1", self.ui.source_gaps.get())
            if status == "denied":
                self.assertIn("拒讀 1", self.ui.source_gaps.get())
        self.assertEqual(self.ui.sources.heading("success", "text"), "最後成功時間（歷史）")
        self.assertEqual(len(self.ui.sources.get_children()), 7)
        self.assertFalse(any(action != "snapshot" for action, _ in self.controller.calls))
        self.assertEqual(before["events"], document["events"])

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

    def test_automatic_checkbox_is_separate_from_receive_checkbox(self):
        self.assertFalse(self.ui.automatic_enabled.get())
        self.ui.agent_check.invoke()
        self.wait_for(lambda: self.controller.value["agent_delivery"]["enabled"] is True)
        self.wait_for(lambda: not self.ui._busy and not self.ui.worker.pending)
        self.assertFalse(any(action == "set_automatic_agent" for action, _ in self.controller.calls))
        self.ui.automatic_executable.set("C:/fixture/codex.exe")
        self.ui.automatic_check.invoke()
        self.wait_for(lambda: self.controller.value["automatic_agent"]["enabled"] is True)
        self.wait_for(lambda: "無事件不呼叫模型" in self.ui.automatic_status.get())
        self.assertTrue(self.ui.agent_enabled.get())
        self.assertTrue(self.ui.automatic_enabled.get())

    def test_readable_summary_is_default_and_raw_checkbox_only_reveals_saved_data(self):
        self.wait_for(lambda: not self.ui.worker.pending)
        self.ui.events.selection_set("synthetic-example-1")
        self.ui.select_event()
        self.wait_for(lambda: "連接埠：43210" in self.ui.detail.get("1.0", "end"))
        summary = self.ui.detail.get("1.0", "end")
        self.assertIn("觀察事實", summary)
        self.assertIn("未知與限制", summary)
        self.assertIn("建議的唯讀查證", summary)
        self.assertNotIn('"binding_facts"', summary)
        self.assertFalse(self.ui.show_raw.get())
        inspections = sum(action == "inspect" for action, _ in self.controller.calls)
        self.ui.raw_check.invoke()
        self.assertIn('"binding_facts"', self.ui.detail.get("1.0", "end"))
        self.ui.raw_check.invoke()
        self.assertNotIn('"binding_facts"', self.ui.detail.get("1.0", "end"))
        self.assertEqual(inspections, sum(action == "inspect" for action, _ in self.controller.calls))
        self.assertFalse(any(action in {"ack", "diagnose", "start"} for action, _ in self.controller.calls))
        self.assertEqual(self.ui.detail.cget("state"), "disabled")

    def test_real_widgets_filter_loaded_rows_and_clear_without_touching_events(self):
        second = {"event_id": "synthetic-example-2", "event_type": "coverage.degraded",
                  "severity": "high", "delivery_status": "ack", "observed_at": "2026-10-23T04:01:00+00:00"}
        self.controller.value["events"].append(second)
        self.controller.value.update(events_total=101, events_truncated=True)
        self.ui._apply_snapshot(copy.deepcopy(self.controller.value))
        before = copy.deepcopy(self.controller.value)
        self.assertEqual(self.ui.events.item("synthetic-example-1", "values")[0], "2026-10-23T04:00:00+00:00")
        self.ui.severity_filter.set("高")
        self.ui.severity_choice.event_generate("<<ComboboxSelected>>")
        self.window.update()
        self.assertEqual(self.ui.events.get_children(), ("synthetic-example-2",))
        self.assertIn("顯示 1 / 已載入 2；儲存總數 101", self.ui.events_note.get())
        self.assertIn("清單已截斷", self.ui.events_note.get())
        self.ui.delivery_filter.set("待接手")
        self.ui.delivery_choice.event_generate("<<ComboboxSelected>>")
        self.window.update()
        self.assertEqual(self.ui.events.get_children(), ())
        self.assertIn("不代表沒有事件或主機安全", self.ui.events_note.get())
        self.ui.clear_filters_button.invoke()
        self.assertEqual(self.ui.events.get_children(), ("synthetic-example-1", "synthetic-example-2"))
        self.assertEqual(self.controller.value, before)
        self.assertFalse(any(action in {"ack", "diagnose", "start", "pause"} for action, _ in self.controller.calls))

    def test_late_inspection_cannot_show_hidden_event_details_after_filter_changes(self):
        entered, release = threading.Event(), threading.Event()
        original = self.controller.inspect
        def inspect(event_id):
            entered.set()
            release.wait(timeout=2)
            return original(event_id)
        self.wait_for(lambda: not self.ui.worker.pending)
        with patch.object(self.controller, "inspect", side_effect=inspect):
            try:
                self.ui.events.selection_set("synthetic-example-1")
                self.ui.select_event()
                self.wait_for(entered.is_set)
                self.ui.severity_filter.set("嚴重")
                self.ui.filter_events()
                release.set()
                self.wait_for(lambda: not self.ui.worker.pending)
                self.wait_for(lambda: self.ui.worker.results.empty())
                self.assertNotIn("synthetic-example-1", self.ui.detail.get("1.0", "end"))
                self.assertIsNone(self.ui._last_event)
            finally:
                release.set()

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

