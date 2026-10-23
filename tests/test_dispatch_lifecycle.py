"""Synthetic dispatcher lifecycle fixtures. No model, network or live event.

The plain-Popen fake used here is explicit test data, never wake evidence.
"""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import unittest
from unittest.mock import patch

from budget_fixtures import isolated_budget
from eventguard import agent_dispatch as dispatch
from eventguard.acceptance_control import read_json, write_json
from test_agent_dispatch import EVENT, RECORD, FAKE, FakeInbox, trace_fixture


class DispatchLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.authority = self.enterContext(isolated_budget(self.root))
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "eventguard.sqlite3").write_bytes(b"synthetic fixture only")
        self.inbox_dir = self.root / "inbox"
        self.inbox = FakeInbox(self.inbox_dir)
        self.script = self.root / "fake.py"
        self.script.write_text(FAKE, encoding="utf-8")
        self.trace = self.root / "fake-trace.json"
        self.trace.write_text(json.dumps(trace_fixture()), encoding="utf-8")
        self.cancel = threading.Event()
        self.children = []
        self.addCleanup(self._join_children)

    def _join_children(self):
        for child in self.children:
            self.assertIsNotNone(child.wait(timeout=8), "Owned synthetic child must exit")

    def fixtures(self):
        stack = ExitStack()
        original = subprocess.Popen

        def launch(*args, **kwargs):
            child = original(*args, **kwargs)
            self.children.append(child)
            return child

        stack.enter_context(patch.object(dispatch, "_inbox", return_value=self.inbox))
        stack.enter_context(patch.object(dispatch.shutil, "which", return_value=sys.executable))
        stack.enter_context(patch.object(dispatch.importlib.util, "find_spec", return_value=True))
        stack.enter_context(patch.object(dispatch, "command", return_value=[
            sys.executable, "-B", str(self.script), str(self.trace), "success"]))
        stack.enter_context(patch.object(dispatch.subprocess, "Popen", side_effect=launch))
        return stack

    def invoke(self, name, **kwargs):
        return dispatch.run(self.root / name, self.source, self.inbox_dir, execute=True,
                            max_tasks=1, max_seconds=5, poll_seconds=.01,
                            deadline_monotonic=time.monotonic()+15, cancel=self.cancel, **kwargs)

    def stop_on_paused(self, target, *, resume=False):
        original = dispatch._save
        states = []

        def save(directory, state):
            original(directory, state)
            states.append(state["state"])
            if state["state"] == "waiting_paused" and not resume:
                self.cancel.set()
        return patch.object(dispatch, "_save", side_effect=save), states

    def test_paused_pending_keeps_event_and_uses_zero_budget(self):
        observer, states = self.stop_on_paused(self.root / "paused")
        with self.fixtures(), observer, patch.object(self.authority, "reserve", wraps=self.authority.reserve) as reserve:
            self.assertEqual(self.invoke("paused", continuous=True, dispatch_enabled=lambda: False), 0)
        self.assertIn("waiting_paused", states)
        reserve.assert_not_called()
        self.assertEqual(self.authority.status()["used"], 0)
        self.assertEqual(self.inbox.pending, EVENT)
        self.assertEqual(self.children, [])
        self.assertFalse((self.root / "paused/attempts").exists())

    def test_callback_exception_is_fail_closed(self):
        def unavailable():
            raise OSError("fixture unavailable")
        observer, _ = self.stop_on_paused(self.root / "failed-control")
        with self.fixtures(), observer:
            self.assertEqual(self.invoke("failed-control", continuous=True, dispatch_enabled=unavailable), 0)
        self.assertEqual(self.children, [])
        self.assertEqual(self.authority.status()["used"], 0)

    def test_pause_during_preparation_does_not_reserve_or_consume_retry(self):
        enabled = [True]
        def prepare(*args, **kwargs):
            enabled[0] = False
            return [sys.executable, "-c", "raise SystemExit(98)"]
        observer, _ = self.stop_on_paused(self.root / "prepare")
        with self.fixtures(), observer, patch.object(dispatch, "command", side_effect=prepare), \
                patch.object(self.authority, "reserve", wraps=self.authority.reserve) as reserve:
            self.assertEqual(self.invoke("prepare", continuous=True, dispatch_enabled=lambda: enabled[0]), 0)
        reserve.assert_not_called()
        self.assertEqual(read_json(self.inbox_dir / "dispatcher-attempts.json")["events"], {})
        self.assertEqual(self.authority.status()["used"], 0)
        self.assertEqual(self.children, [])

    def test_pause_during_reference_read_is_rechecked_before_reserve(self):
        enabled = [True]
        original_reference = self.inbox.delivery_reference
        def reference(identity):
            enabled[0] = False
            return original_reference(identity)
        observer, _ = self.stop_on_paused(self.root / "reference")
        with self.fixtures(), observer, patch.object(self.inbox, "delivery_reference", side_effect=reference), \
                patch.object(self.authority, "reserve", wraps=self.authority.reserve) as reserve:
            self.assertEqual(self.invoke("reference", continuous=True, dispatch_enabled=lambda: enabled[0]), 0)
        reserve.assert_not_called()
        self.assertEqual(self.authority.status()["used"], 0)
        self.assertEqual(self.children, [])

    def test_pause_after_reservation_retains_charge_but_does_not_spawn(self):
        enabled = [True]
        original_reserve = self.authority.reserve
        def reserve(*args, **kwargs):
            value = original_reserve(*args, **kwargs)
            enabled[0] = False
            return value
        observer, _ = self.stop_on_paused(self.root / "reserved")
        with self.fixtures(), observer, patch.object(self.authority, "reserve", side_effect=reserve):
            self.assertEqual(self.invoke("reserved", continuous=True, dispatch_enabled=lambda: enabled[0]), 0)
        budget = self.authority.status()
        self.assertEqual(budget["used"], 1)
        self.assertIsNone(budget["active"])
        record = read_json(self.inbox_dir / "dispatcher-attempts.json")["events"][EVENT][0]
        self.assertEqual(record["state"], "not_started")
        self.assertEqual(record["reason"], "paused_before_worker_launch")
        self.assertTrue(record["child_exited"])
        self.assertEqual(self.children, [])
        self.assertEqual(self.inbox.pending, EVENT)

    def test_resume_same_owner_admits_once_without_resetting_budget(self):
        enabled = [False]
        original_save = dispatch._save
        states = []
        target = self.root / "resume"
        def save(directory, state):
            states.append(state["state"])
            original_save(directory, state)
            if state["state"] == "waiting_paused":
                enabled[0] = True
        def pending():
            if self.children:
                dispatch.stop(target)
                return None
            return EVENT
        with self.fixtures(), patch.object(dispatch, "_save", side_effect=save), \
                patch.object(self.inbox, "pending_event_id", side_effect=pending):
            self.assertEqual(self.invoke("resume", continuous=True, dispatch_enabled=lambda: enabled[0]), 0)
        saved = dispatch.status(target, read_only=True)
        self.assertIn("waiting_paused", states)
        self.assertEqual(saved["tasks_started"], 1)
        self.assertEqual(saved["tasks_passed"], 1)
        self.assertEqual(self.authority.status()["used"], 1)
        self.assertEqual(len(self.children), 1)
        for stage in ("capture_worker_started", "cli_started", "event_received", "evidence_queried",
                      "result_saved", "outbox_acknowledged", "provider_turn_completed", "owned_tree_exited"):
            self.assertTrue(saved["delivery_progress"][stage], stage)
        self.assertFalse(saved["delivery_progress"]["notification_submitted"])

    def test_alternate_root_uses_its_config_and_working_directory(self):
        from eventguard.runtime import Runtime
        alternate = self.root / "alternate-project"
        alternate.mkdir()
        seen = []
        def config(runtime):
            seen.append(runtime.root)
            return {}
        def pending():
            self.cancel.set()
            return None
        with self.fixtures(), patch.object(Runtime, "config", config), \
                patch.object(self.inbox, "pending_event_id", side_effect=pending):
            self.assertEqual(self.invoke("alternate", root=alternate), 0)
        self.assertEqual(seen, [alternate])
        self.assertEqual(dispatch.status(self.root / "alternate")["project_root"], str(alternate))
        args = dispatch.command("codex.exe", "python.exe", self.source, self.inbox_dir,
                                EVENT, self.root, root=alternate)
        self.assertEqual(args[args.index("-C")+1], str(alternate))
        mcp_config = tomllib.loads(next(arg for arg in args if arg.startswith("mcp_servers.")))
        server_args = mcp_config["mcp_servers"]["eventguard_inbox"]["args"]
        self.assertEqual(server_args[server_args.index("--project-root")+1], str(alternate))

    def test_missing_executable_retains_pending_without_budget_or_child(self):
        with self.fixtures(), patch.object(dispatch.shutil, "which", return_value=None):
            self.assertEqual(self.invoke("offline"), 2)
        self.assertEqual(self.inbox.pending, EVENT)
        self.assertEqual(self.authority.status()["used"], 0)
        self.assertEqual(self.children, [])

    def test_selection_failure_is_blocked_instead_of_an_empty_queue(self):
        def select(inbox):
            self.assertIs(inbox, self.inbox)
            raise KeyError("fixture selection unavailable")
        with self.fixtures():
            self.assertEqual(self.invoke("select-failed", select_event=select), 2)
        saved = dispatch.status(self.root / "select-failed", read_only=True)
        self.assertEqual(saved["state"], "blocked")
        self.assertEqual(saved["reason"], "dispatch_selection_failed_pending_preserved")
        self.assertEqual(self.inbox.pending, EVENT)
        self.assertEqual(self.authority.status()["used"], 0)
        self.assertEqual(self.children, [])

    def test_selection_callback_does_not_use_raw_queue_head(self):
        def select(inbox):
            self.assertIs(inbox, self.inbox)
            self.cancel.set()
            return None
        with self.fixtures(), patch.object(self.inbox, "pending_event_id", side_effect=AssertionError("No raw-head read")):
            self.assertEqual(self.invoke("select-empty", select_event=select), 0)
        self.assertEqual(self.authority.status()["used"], 0)
        self.assertEqual(self.children, [])

    def test_status_failure_after_reservation_does_not_erase_charged_intent(self):
        from eventguard.agent_budget import BudgetError
        with self.fixtures(), patch.object(self.authority, "status", side_effect=BudgetError("budget_unavailable")):
            self.assertEqual(self.invoke("post-reserve-status"), 1)
        budget = self.authority.status()
        self.assertEqual(budget["used"], 1)
        self.assertIsNone(budget["active"])
        record = read_json(self.inbox_dir / "dispatcher-attempts.json")["events"][EVENT][0]
        self.assertEqual(record["state"], "not_started")
        self.assertTrue(record["child_exited"])
        self.assertEqual(self.children, [])


class DispatchProofTests(unittest.TestCase):
    def test_partial_tool_receipts_are_separate_from_ack_and_completion(self):
        record = deepcopy(RECORD)
        record.pop("result")
        summary = dispatch.assess_delivery(trace_fixture()[:2], record, EVENT, 7, False)
        self.assertFalse(summary["passed"])
        self.assertTrue(summary["event_received"])
        self.assertTrue(summary["evidence_queried"])
        self.assertFalse(summary["result_saved"])
        self.assertFalse(summary["outbox_acknowledged"])
        self.assertFalse(summary["provider_turn_completed"])

    def test_model_text_and_queue_sender_exit_are_not_tool_receipts(self):
        trace = [{"type": "item.completed", "item": {"type": "agent_message", "text": "ACK success"}},
                 {"type": "turn.completed"}]
        summary = dispatch.assess_delivery(trace, {}, EVENT, 0, False)
        self.assertFalse(summary["passed"])
        self.assertFalse(summary["event_received"])
        self.assertFalse(summary["evidence_queried"])
        self.assertFalse(summary["result_saved"])

    def test_wrong_server_or_error_does_not_verify_receive_stage(self):
        for field, value in (("server", "untrusted"), ("error", "failed"), ("status", "failed")):
            trace = trace_fixture()
            trace[0]["item"][field] = value
            summary = dispatch.assess_delivery(trace, deepcopy(RECORD), EVENT, 0, True)
            self.assertFalse(summary["passed"])
            self.assertFalse(summary["event_received"])
            self.assertFalse(summary["evidence_queried"])


class DispatchReadonlyAndWorkerGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_id, self.token = "a"*32, "b"*32
        write_json(self.root / "dispatch.json", {"kind": dispatch.KIND, "run_id": self.run_id})
        self.state = {"kind": dispatch.KIND, "run_id": self.run_id, "state": "running",
                      "active_attempt_id": self.token, "child_exited": False}
        write_json(self.root / "status.json", self.state)
        self.attempt = self.root / "attempts" / self.token
        self.attempt.mkdir(parents=True)
        write_json(self.attempt / "attempt.json", {"run_id": self.run_id, "attempt_id": self.token})
        self.control = self.root / "control.json"

    def manifest(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_readonly_status_never_creates_capture_lock_for_saved_receipt(self):
        write_json(self.attempt / "capture-exit.json", {"attempt_id": self.token})
        before = self.manifest()
        result = dispatch.status(self.root, read_only=True)
        self.assertFalse(result["child_exited"])
        self.assertEqual(self.manifest(), before)
        self.assertFalse((self.attempt / "capture.lock").exists())

    def test_readonly_status_never_creates_capture_lock_for_skipped_worker(self):
        write_json(self.attempt / "capture-skipped.json", {"attempt_id": self.token,
                   "launch_not_started": True, "capture_complete": False})
        before = self.manifest()
        dispatch.status(self.root, read_only=True)
        self.assertEqual(self.manifest(), before)

    def worker(self, capture):
        args = ["_capture", "--attempt-dir", str(self.attempt), "--attempt-id", self.token,
                "--deadline-monotonic", str(time.monotonic()+20), "--stop-run-dir", str(self.root),
                "--run-id", self.run_id, "--admission-path", str(self.control),
                "--admission-run-id", self.run_id, "--", sys.executable, "-c", "pass"]
        with patch.object(dispatch, "capture", side_effect=capture):
            return dispatch.main(args)

    def write_control(self, **overrides):
        value = {"kind": "eventguard-agent-service-control-v1", "enabled": True,
                 "paused": False, "run_id": self.run_id}
        value.update(overrides)
        write_json(self.control, value)

    def test_worker_rechecks_durable_pause_and_generation_before_cli_launch(self):
        for overrides in ({"paused": True}, {"enabled": False}, {"run_id": "c"*32},
                          {"enabled": 1}, {"paused": None}):
            self.write_control(**overrides)
            def capture(*args, **kwargs):
                self.assertFalse(kwargs["start_allowed"]())
                self.assertFalse(kwargs["stop_requested"](), "Pause must not cancel an active CLI")
                return 4
            self.assertEqual(self.worker(capture), 4)

    def test_worker_control_read_failure_blocks_launch_but_does_not_cancel_active(self):
        def capture(*args, **kwargs):
            self.assertFalse(kwargs["start_allowed"]())
            self.assertFalse(kwargs["stop_requested"]())
            return 4
        self.assertEqual(self.worker(capture), 4)

    def test_worker_pause_after_start_does_not_cancel_active_cli(self):
        self.write_control()
        def capture(*args, **kwargs):
            self.assertTrue(kwargs["start_allowed"]())
            self.write_control(paused=True)
            self.assertFalse(kwargs["start_allowed"]())
            self.assertFalse(kwargs["stop_requested"]())
            dispatch.stop(self.root)
            self.assertTrue(kwargs["stop_requested"]())
            return 0
        self.assertEqual(self.worker(capture), 0)

    def test_owned_supervisor_exit_is_required_for_new_managed_attempt(self):
        write_json(self.attempt / "capture-start.json", {})
        (self.attempt / "codex.jsonl").write_text("", encoding="utf-8")
        record = {"run_dir": str(self.root), "run_id": self.run_id, "attempt_id": self.token,
                  "event_id": EVENT, "supervisor_exit_required": True}
        inbox = FakeInbox(self.root / "inbox")
        with patch.object(dispatch, "validate_receipt", return_value=[]), \
                patch.object(dispatch, "assess_delivery", return_value={"passed": True, "evidence_errors": []}):
            summary = dispatch._complete(record, inbox, {"codex_exit_code": 0,
                    "stdout_truncated": False, "stderr_truncated": False})
        self.assertFalse(summary["passed"])
        self.assertFalse(summary["child_exited"])
        self.assertEqual(record["state"], "started")
        self.assertIn("supervisor_tree_exit_unconfirmed", summary["evidence_errors"])


if __name__ == "__main__":
    unittest.main()
