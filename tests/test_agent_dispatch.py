"""Dispatcher safety tests with an explicitly fake CLI; no real agent evidence."""
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

from eventguard.acceptance_control import FileLease, read_json, write_json
from budget_fixtures import isolated_budget, reserve_capture
from eventguard.agent_dispatch import (ROOT, KIND, PROMPT, TOOLS, assess_delivery,
                                       command, main, run, status, stop)


EVENT = "synthetic-dispatch-test"
RECORD = {"event_id": EVENT, "snapshot": {"event_id": EVENT, "event_type": "coverage_changed",
          "severity": "warning", "synthetic": True, "coverage": {"defender": "partial"}},
          "received_at": "2026-10-22T10:00:00+00:00", "query_id": "query-test",
          "result": {"status": "review_recorded", "event_id": EVENT,
          "query_id": "query-test", "decision": "reviewed_metadata", "result_id": "result-test",
          "recorded_at": "2026-10-22T10:00:01+00:00", "incident_conclusion": "not_assessed",
          "real_agent_wake_verified": False}}


def trace_fixture():
    received = {"status": "event_available", "event_id": EVENT, "snapshot": RECORD["snapshot"],
                "received_at": RECORD["received_at"]}
    queried = {"status": "stored_minimal_snapshot", "event_id": EVENT, "query_id": "query-test",
               "snapshot": RECORD["snapshot"], "snapshot_only": True, "system_query_executed": False}
    replies = [received, queried, {**RECORD["result"], "outbox_acknowledged": True}]
    args = [{}, {"event_id": EVENT}, {"event_id": EVENT, "query_id": "query-test", "decision": "reviewed_metadata"}]
    return [{"type": "item.completed", "item": {"id": "call-" + str(number), "type": "mcp_tool_call",
             "server": "eventguard_inbox", "tool": tool, "status": "completed", "error": None,
             "arguments": arg, "result": {"content": [{"type": "text", "text": json.dumps(reply)}]}}}
            for number, (tool, arg, reply) in enumerate(zip(TOOLS, args, replies))] + [{"type": "turn.completed"}]


FAKE = """import json,os,sys,time
rows=json.load(open(sys.argv[1],encoding='utf-8'))
mode=sys.argv[2]
if mode=='slow':
 open(sys.argv[1]+'.ready','w').close()
 end=time.monotonic()+60
 while not os.path.exists(sys.argv[1]+'.release') and time.monotonic()<end: time.sleep(.02)
if mode=='fail': rows=rows[:2]+[{'type':'turn.failed'}]
for row in rows: print(json.dumps(row),flush=True)
raise SystemExit(7 if mode=='fail' else 0)
"""

FAKE_QUEUE = """import json,sys
sys.path.insert(0,sys.argv[5])
from eventguard.queue_inbox import QueueInbox
backend=QueueInbox(sys.argv[1],sys.argv[2],event_id=sys.argv[3])
def output(tool,args,reply):
 print(json.dumps({'type':'item.completed','item':{'id':'fake-'+tool,'type':'mcp_tool_call','server':'eventguard_inbox','tool':tool,'status':'completed','error':None,'arguments':args,'result':{'content':[{'type':'text','text':json.dumps(reply)}]}}}),flush=True)
reply=backend.receive_event()
event=reply['event_id']
output('receive_event',{},reply)
query=backend.query_evidence(event)
output('query_evidence',{'event_id':event},query)
if sys.argv[4]=='fail':
 print(json.dumps({'type':'turn.failed'}),flush=True)
 raise SystemExit(7)
ack=backend.ack_event(event,query['query_id'],'reviewed_metadata')
output('ack_event',{'event_id':event,'query_id':query['query_id'],'decision':'reviewed_metadata'},ack)
print(json.dumps({'type':'turn.completed'}),flush=True)
"""


class FakeInbox:
    """Synthetic fixture backend; cannot claim actual delivery or persist an ACK."""
    def __init__(self, state, pending=EVENT):
        state.mkdir(parents=True, exist_ok=True)
        self.pending = pending
        self.acked = True

    def pending_event_id(self):
        return self.pending

    def delivery_reference(self, event_id):
        return {"event_id": event_id, "namespace": "test", "payload_hash": "1"*64}

    def evidence(self, event_id):
        return deepcopy(RECORD)

    def acknowledged(self, event_id):
        return self.acked


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.authority = self.enterContext(isolated_budget(self.directory))
        self.source = self.directory / "source"
        self.source.mkdir()
        (self.source / "eventguard.sqlite3").write_bytes(b"explicit fake fixture")
        self.state_dir = self.directory / "state"
        self.backend = FakeInbox(self.state_dir)
        self.script = self.directory / "fake.py"
        self.script.write_text(FAKE, encoding="utf-8")
        self.trace = self.directory / "fake-trace.json"
        self.trace.write_text(json.dumps(trace_fixture()), encoding="utf-8")
        self.children = []
        self.addCleanup(self.wait_children)

    def wait_children(self):
        for child in self.children:
            self.assertIsNotNone(child.wait(timeout=8), "Owned fake child must exit naturally")

    def fixtures(self, mode="success"):
        stack = ExitStack()
        self.backend.acked = mode != "fail"
        original = subprocess.Popen

        def launch(*args, **kwargs):
            child = original(*args, **kwargs)
            self.children.append(child)
            return child

        stack.enter_context(patch("eventguard.agent_dispatch._inbox", return_value=self.backend))
        stack.enter_context(patch("eventguard.agent_dispatch.shutil.which", return_value=sys.executable))
        stack.enter_context(patch("eventguard.agent_dispatch.importlib.util.find_spec", return_value=True))
        stack.enter_context(patch("eventguard.agent_dispatch.command", return_value=[sys.executable, "-B", str(self.script), str(self.trace), mode]))
        stack.enter_context(patch("eventguard.agent_dispatch.subprocess.Popen", side_effect=launch))
        return stack

    def invoke(self, name, **kwargs):
        return run(self.directory / name, self.source, self.state_dir, max_tasks=1,
                   max_seconds=kwargs.pop("max_seconds", 15), execute=kwargs.pop("execute", True), **kwargs)

    def test_scoped_command_and_prompt_no_preloaded_event(self):
        args = command("codex.exe", Path("C:/Python313/python.exe"), self.source, self.state_dir,
                       EVENT, self.directory, allow_live=True)
        server = tomllib.loads(next(arg for arg in args if arg.startswith("mcp_servers.")))["mcp_servers"]["eventguard_inbox"]
        self.assertEqual(server["enabled_tools"], list(TOOLS))
        self.assertEqual(server["tools"], {tool: {"approval_mode": "approve"} for tool in TOOLS})
        self.assertIn("--allow-live", server["args"])
        self.assertIn("features.shell_tool=false", args)
        self.assertIn("features.unbounded_connection_retries=false", args)
        self.assertIn("mcp_servers.eventguard_test.enabled=false", args)
        self.assertIn("mcp_servers.eventguard.enabled=false", args)
        self.assertIn("mcp_servers.eventguard-app.enabled=false", args)
        self.assertNotIn(EVENT, PROMPT)
        self.assertFalse(any("bypass" in arg for arg in args))

    def test_project_chat_servers_disabled_for_each_event_bound_mode(self):
        for allow_live in (False, True):
            for allow_ack in (False, True):
                with self.subTest(allow_live=allow_live, allow_ack=allow_ack):
                    args = command("codex.exe", "python.exe", self.source, self.state_dir,
                                   EVENT, self.directory, allow_live=allow_live, allow_ack=allow_ack)
                    overrides = [args[index + 1] for index, value in enumerate(args[:-1]) if value == "-c"]
                    config = tomllib.loads("\n".join(overrides))
                    servers = config["mcp_servers"]
                    self.assertEqual(set(servers), {"eventguard_inbox", "eventguard_test", "eventguard", "eventguard-app"})
                    self.assertEqual(servers["eventguard_test"], {"enabled": False})
                    self.assertEqual(servers["eventguard"], {"enabled": False})
                    # Use the actual registered server ID. Tool namespaces use
                    # underscores, but that is not a configuration alias.
                    self.assertEqual(servers["eventguard-app"], {"enabled": False})
                    self.assertEqual(servers["eventguard_inbox"]["enabled_tools"],
                                     list(TOOLS if allow_ack else TOOLS[:2]))
                    self.assertEqual(args[-1], "-")

    def test_no_execute_and_no_event_make_zero_cli_calls(self):
        with self.fixtures():
            self.assertEqual(self.invoke("preflight", execute=False), 0)
            self.backend.pending = None
            self.assertEqual(self.invoke("idle", max_seconds=.08, poll_seconds=.01), 0)
        self.assertEqual(self.children, [])
        self.assertEqual(status(self.directory / "preflight")["state"], "preflight_ready")
        self.assertEqual(status(self.directory / "idle")["state"], "time_limit_reached")

    def test_watch_idle_outlasts_task_timeout_without_attempt_or_model(self):
        self.backend.pending = None
        began = time.monotonic()
        cancel, reads = threading.Event(), []
        def pending():
            reads.append(True)
            if len(reads) >= 3:
                cancel.set()
            return None
        with self.fixtures(), patch("eventguard.agent_dispatch.command", side_effect=AssertionError("No idle CLI")), \
                patch.object(self.backend, "pending_event_id", side_effect=pending):
            code = self.invoke("watch-idle", continuous=True, max_seconds=.01,
                               deadline_monotonic=began + 30, cancel=cancel, poll_seconds=.01)
        saved = status(self.directory / "watch-idle")
        self.assertEqual(code, 0)
        self.assertTrue(saved["continuous"])
        self.assertEqual(saved["state"], "stopped")
        self.assertGreaterEqual(saved["queue_checks"], 2)
        self.assertEqual(saved["tasks_started"], 0)
        self.assertIn("last_checked_at", saved)
        self.assertFalse((self.directory / "watch-idle/attempts").exists())
        self.assertEqual(self.authority.status()["used"], 0)
        self.assertEqual(self.children, [])

    def test_watch_receives_after_idle_then_remains_waiting_until_cooperative_stop(self):
        target = self.directory / "watch-receive"
        reads = []

        def pending():
            reads.append(time.monotonic())
            if len(reads) <= 3:
                return None
            if not self.children:
                return EVENT
            stop(target)
            return None

        with self.fixtures(), patch.object(self.backend, "pending_event_id", side_effect=pending):
            self.assertEqual(self.invoke("watch-receive", continuous=True, max_seconds=5,
                                         poll_seconds=.01), 0)
        saved = status(target)
        self.assertEqual(saved["state"], "stopped")
        self.assertEqual(saved["tasks_started"], 1)
        self.assertEqual(saved["tasks_passed"], 1)
        self.assertEqual(saved["events_total"], 1)
        self.assertEqual(len(self.children), 1)
        self.assertTrue(saved["child_exited"])

    def test_watch_exhausted_budget_keeps_pending_without_creating_attempts(self):
        seen = []
        cancel = threading.Event()
        original_save = __import__("eventguard.agent_dispatch", fromlist=["_save"])._save

        def observe(directory, value):
            seen.append((value["state"], value.get("reason")))
            original_save(directory, value)
            if value["state"] == "waiting_budget":
                cancel.set()

        with self.fixtures(), patch.object(self.authority, "status", return_value={
                "state": "blocked", "reason": "budget_exhausted", "remaining": 0}), \
             patch("eventguard.agent_dispatch._save", side_effect=observe), \
             patch.object(self.authority, "reserve", side_effect=AssertionError("No exhausted-budget reservation")):
            self.assertEqual(self.invoke("watch-budget", continuous=True, max_seconds=.01,
                deadline_monotonic=time.monotonic()+30, cancel=cancel, poll_seconds=.01), 0)
        self.assertIn(("waiting_budget", "budget_exhausted"), seen)
        self.assertEqual(self.backend.pending, EVENT)
        self.assertFalse((self.directory / "watch-budget/attempts").exists())
        self.assertEqual(self.children, [])

    def test_watch_budget_rechecks_in_same_owner_and_resumes_when_ready(self):
        from eventguard import agent_dispatch
        original_status = self.authority.status
        checks = []
        target = self.directory / "watch-budget-ready"

        def budget_status():
            checks.append(True)
            if len(checks) < 3:
                return {"state": "blocked", "reason": "budget_exhausted", "remaining": 0}
            return original_status()

        def pending():
            if self.children:
                stop(target)
                return None
            return EVENT

        with self.fixtures(), patch.object(self.authority, "status", side_effect=budget_status), \
             patch.object(self.backend, "pending_event_id", side_effect=pending), \
             patch.object(agent_dispatch, "BUDGET_CHECK_SECONDS", .01):
            self.assertEqual(self.invoke("watch-budget-ready", continuous=True, max_seconds=5,
                                        poll_seconds=.01), 0)
        saved = status(target)
        self.assertEqual(saved["state"], "stopped")
        self.assertEqual(saved["tasks_passed"], 1)
        self.assertGreaterEqual(len(checks), 3)
        self.assertEqual(len(list((target/"attempts").iterdir())), 1)
        self.assertEqual(len(self.children), 1)

    def test_watch_refused_admission_latches_same_event_even_when_status_ready(self):
        from eventguard.agent_budget import BudgetError
        target = self.directory / "watch-admission-refused"
        reads = []
        seen = []
        original_save = __import__("eventguard.agent_dispatch", fromlist=["_save"])._save

        def pending():
            reads.append(True)
            if len(reads) >= 6:
                stop(target)
            return EVENT

        def observe(directory, value):
            seen.append((value["state"], value.get("reason")))
            original_save(directory, value)

        with self.fixtures(), patch.object(self.backend, "pending_event_id", side_effect=pending), \
             patch.object(self.authority, "status", return_value={"state": "ready", "remaining": 5}), \
             patch.object(self.authority, "reserve", side_effect=BudgetError("budget_per_event_exhausted")) as reserve, \
             patch("eventguard.agent_dispatch._save", side_effect=observe), \
             patch("eventguard.agent_dispatch.BUDGET_CHECK_SECONDS", .001):
            self.assertEqual(self.invoke("watch-admission-refused", continuous=True, poll_seconds=.01), 0)
        reserve.assert_called_once()
        self.assertGreaterEqual(len(reads), 6)
        self.assertIn(("waiting_attention", "budget_per_event_exhausted"), seen)
        self.assertEqual(status(target)["state"], "stopped")
        self.assertEqual(status(target)["tasks_started"], 0)
        self.assertEqual(len(list((target/"attempts").iterdir())), 1)
        self.assertEqual(self.backend.pending, EVENT)
        self.assertEqual(self.children, [])

    def test_watch_admission_latch_releases_only_when_pending_event_changes(self):
        from eventguard.agent_budget import BudgetError
        target = self.directory / "watch-admission-next"
        reads = []

        def pending():
            reads.append(True)
            if len(reads) >= 9:
                stop(target)
            return EVENT if len(reads) <= 4 else "synthetic-other"

        with self.fixtures(), patch.object(self.backend, "pending_event_id", side_effect=pending), \
             patch.object(self.authority, "status", return_value={"state": "ready", "remaining": 5}), \
             patch.object(self.authority, "reserve", side_effect=BudgetError("budget_per_event_exhausted")) as reserve, \
             patch("eventguard.agent_dispatch.BUDGET_CHECK_SECONDS", .001):
            self.assertEqual(self.invoke("watch-admission-next", continuous=True, poll_seconds=.01), 0)
        self.assertEqual(reserve.call_count, 2)
        self.assertEqual([call.args[1] for call in reserve.call_args_list], [EVENT, "synthetic-other"])
        self.assertEqual(len(list((target/"attempts").iterdir())), 2)
        self.assertEqual(self.children, [])

    def test_watch_failed_delivery_waits_for_human_without_retry(self):
        target = self.directory / "watch-failed"
        reads = []
        seen = []
        original_save = __import__("eventguard.agent_dispatch", fromlist=["_save"])._save

        def pending():
            reads.append(True)
            if len(reads) > 4:
                stop(target)
            return EVENT

        def observe(directory, value):
            seen.append((value["state"], value.get("reason")))
            original_save(directory, value)

        with self.fixtures("fail"), patch.object(self.backend, "pending_event_id", side_effect=pending), \
             patch("eventguard.agent_dispatch._save", side_effect=observe):
            self.assertEqual(self.invoke("watch-failed", continuous=True, poll_seconds=.01), 0)
        self.assertIn(("waiting_attention", "delivery_evidence_failed_no_automatic_retry"), seen)
        self.assertEqual(status(target)["tasks_started"], 1)
        self.assertEqual(status(target)["tasks_passed"], 0)
        self.assertEqual(len(list((target/"attempts").iterdir())), 1)
        self.assertEqual(len(self.children), 1)
        self.assertEqual(self.backend.pending, EVENT)

    def test_watch_preflight_and_already_cancelled_never_start_model(self):
        cancellation = threading.Event()
        cancellation.set()
        with self.fixtures():
            self.assertEqual(self.invoke("watch-preflight", execute=False, continuous=True), 0)
            self.assertEqual(self.invoke("watch-cancelled", continuous=True, cancel=cancellation), 0)
        self.assertTrue(status(self.directory/"watch-preflight")["continuous"])
        self.assertEqual(status(self.directory/"watch-cancelled")["state"], "stopped")
        self.assertEqual(self.children, [])

    def test_watch_cli_maps_to_continuous_without_changing_normal_run(self):
        from eventguard import agent_dispatch
        with patch.object(agent_dispatch, "run", return_value=0) as runner, \
             patch.object(agent_dispatch, "status", return_value={"state": "stopped"}), \
             patch("builtins.print"):
            self.assertEqual(main(["watch", "--run-dir", str(self.directory/"cli-watch")]), 0)
            self.assertIs(runner.call_args.kwargs["continuous"], True)
            self.assertIs(runner.call_args.kwargs["execute"], False)
            self.assertEqual(main(["run", "--run-dir", str(self.directory/"cli-run")]), 0)
            self.assertIs(runner.call_args.kwargs["continuous"], False)

    def test_owned_fake_capture_pass_and_receipt(self):
        with self.fixtures():
            self.assertEqual(self.invoke("success"), 0)
        saved = status(self.directory / "success")
        self.assertEqual(saved["state"], "task_limit_reached")
        self.assertEqual(saved["tasks_started"], 1)
        self.assertEqual(saved["tasks_passed"], 1)
        self.assertTrue(saved["child_exited"])
        attempt = self.directory / "success/attempts" / saved["active_attempt_id"]
        self.assertTrue(read_json(attempt / "capture-exit.json")["capture_complete"])
        self.assertTrue(read_json(attempt / "summary.json")["passed"])

    def test_explicit_retry_only_and_durable_three_attempt_budget(self):
        with self.fixtures("fail"):
            for number in range(3):
                self.assertEqual(self.invoke("failed-" + str(number)), 1)
                self.assertEqual(len(self.children), number + 1, "No immediate automatic model retry")
            self.assertEqual(self.invoke("exhausted"), 1)
        self.assertEqual(len(self.children), 3)
        self.assertEqual(status(self.directory / "exhausted")["reason"], "event_attempt_budget_exhausted")

    def test_unknown_child_refuses_new_run_and_receipt_token_must_match(self):
        ready = Path(str(self.trace) + ".ready")
        release = Path(str(self.trace) + ".release")
        try:
            with self.fixtures("slow"):
                # Advance only the parent dispatcher clock after the fake CLI
                # has really started; cold imports cannot turn this into a
                # pre-launch expiry test. The capture worker keeps real time.
                with patch("eventguard.agent_dispatch.time", wraps=time) as clock:
                    clock.monotonic.side_effect = lambda: time.monotonic() + (120 if ready.exists() else 0)
                    self.assertEqual(self.invoke("pending", max_seconds=60), 3)
                self.assertTrue(ready.exists())
                self.assertEqual(self.invoke("refused"), 3)
            self.assertEqual(len(self.children), 1)
            self.assertEqual(status(self.directory / "refused")["reason"], "prior_child_exit_unconfirmed")
        finally:
            release.write_text("release", encoding="ascii")
        self.children[0].wait(timeout=10)
        self.assertTrue(status(self.directory / "pending")["child_exited"])
        saved = status(self.directory / "pending")
        path = self.directory / "pending/attempts" / saved["active_attempt_id"] / "capture-exit.json"
        receipt = read_json(path)
        receipt["attempt_id"] = "f" * 32
        write_json(path, receipt)
        self.assertFalse(status(self.directory / "pending")["child_exited"])

    def test_source_lease_and_channel_binding_block_alternate_state(self):
        lease = FileLease(self.source / "agent-dispatch.lock")
        self.assertTrue(lease.acquire())
        try:
            with self.fixtures():
                self.assertEqual(self.invoke("busy"), 3)
        finally:
            lease.release()
        self.backend.pending = None
        cancel = threading.Event()
        def bound_then_stop():
            cancel.set()
            return None
        with self.fixtures(), patch.object(self.backend, "pending_event_id", side_effect=bound_then_stop):
            self.assertEqual(self.invoke("bind", cancel=cancel, poll_seconds=.01), 0)
            self.assertEqual(run(self.directory / "alternate", self.source, self.directory / "other-state",
                                 execute=True, max_seconds=15), 2)
        self.assertEqual(status(self.directory / "alternate")["reason"], "dispatch_source_already_bound_to_other_state")
        self.assertEqual(self.children, [])

    def test_stop_idle_is_cooperative_and_starts_no_model(self):
        self.backend.pending = None
        target = self.directory / "stopped"
        result = []

        def stop_during_pending_read():
            result.append(stop(target))
            return None

        with self.fixtures(), patch.object(self.backend, "pending_event_id", side_effect=stop_during_pending_read):
            code = self.invoke("stopped", poll_seconds=.01)
        self.assertEqual(code, 0)
        self.assertEqual(status(target)["state"], "stopped")
        self.assertFalse(result[0]["process_signal_sent"])
        self.assertEqual(self.children, [])

    def test_final_stop_and_deadline_check_prevents_launch_after_slow_preparation(self):
        for label, request_stop in (("deadline", False), ("stop", True)):
            target = self.directory / ("prelaunch-" + label)

            def prepare(*args, **kwargs):
                if request_stop:
                    stop(target)
                else:
                    time.sleep(.08)
                return [sys.executable, "-B", str(self.script), str(self.trace), "success"]

            with self.fixtures(), patch("eventguard.agent_dispatch.command", side_effect=prepare):
                self.assertEqual(self.invoke("prelaunch-" + label, max_seconds=.05 if not request_stop else 5), 0)
            saved = status(target)
            self.assertEqual(saved["tasks_started"], 0)
            self.assertTrue(saved["child_exited"])
            self.assertEqual(saved["state"], "stopped" if request_stop else "time_limit_reached")
        self.assertEqual(self.children, [])
        with self.fixtures():
            self.assertEqual(self.invoke("after-prelaunch-cancel"), 0, "No unconfirmed child is invented")

    def test_shared_cancel_and_absolute_deadline_never_extend_or_launch(self):
        cancel = threading.Event()
        cancel.set()
        with self.fixtures():
            self.assertEqual(self.invoke("already-cancelled", cancel=cancel), 0)
            self.assertEqual(self.invoke("already-expired", deadline_monotonic=time.monotonic() - 1), 0)
        self.assertEqual(status(self.directory / "already-cancelled")["state"], "stopped")
        self.assertEqual(status(self.directory / "already-expired")["state"], "time_limit_reached")
        cancel.clear()

        def prepare(*args, **kwargs):
            cancel.set()
            return [sys.executable, "-B", str(self.script), str(self.trace), "success"]

        with self.fixtures(), patch("eventguard.agent_dispatch.command", side_effect=prepare):
            self.assertEqual(self.invoke("cancel-during-prepare", cancel=cancel), 0)
        self.assertEqual(status(self.directory / "cancel-during-prepare")["state"], "stopped")
        self.assertEqual(self.children, [])

    def test_internal_worker_rechecks_deadline_and_records_no_native_launch(self):
        target = self.directory / "worker-expired"
        with self.fixtures():
            self.assertEqual(self.invoke("worker-expired", execute=False), 0)
        saved = status(target)
        token = "a" * 32
        attempt = target / "attempts" / token
        attempt.mkdir(parents=True)
        write_json(attempt / "attempt.json", {"run_id": saved["run_id"], "attempt_id": token})
        reserve_capture(self.authority, [sys.executable, "-c", "raise SystemExit(99)"], attempt, token, PROMPT)
        with patch("eventguard.acceptance_process.subprocess.Popen", side_effect=AssertionError("Native launch forbidden")):
            self.assertEqual(main(["_capture", "--attempt-dir", str(attempt), "--attempt-id", token,
                "--deadline-monotonic", str(time.monotonic() - 1), "--stop-run-dir", str(target),
                "--run-id", saved["run_id"], "--", sys.executable, "-c", "raise SystemExit(99)"]), 4)
        self.assertEqual(read_json(attempt / "capture-skipped.json"),
                         {"attempt_id": token, "launch_not_started": True, "capture_complete": False})
        self.assertFalse((attempt / "capture-start.json").exists())
        self.assertFalse((attempt / "capture-exit.json").exists())
        self.assertEqual((attempt / "codex.jsonl").read_bytes(), b"")

    def test_stop_between_supervisor_and_native_launch_is_not_an_unknown_child(self):
        target = self.directory / "native-gate-stop"
        original = subprocess.Popen

        def stop_then_launch(*args, **kwargs):
            stop(target)
            child = original(*args, **kwargs)
            self.children.append(child)
            return child

        with self.fixtures(), patch("eventguard.agent_dispatch.subprocess.Popen", side_effect=stop_then_launch):
            self.assertEqual(self.invoke("native-gate-stop"), 0)
        saved = status(target)
        self.assertEqual(saved["state"], "stopped")
        self.assertEqual(saved["tasks_started"], 0)
        self.assertTrue(saved["child_exited"])
        attempt = target / "attempts" / saved["active_attempt_id"]
        self.assertTrue(read_json(attempt / "capture-skipped.json")["launch_not_started"])
        self.assertFalse((attempt / "capture-start.json").exists())
        with self.fixtures():
            self.assertEqual(self.invoke("after-native-gate-stop"), 0)

    def test_proof_rejects_text_only_ack_wrong_ids_and_extra_tools(self):
        self.assertTrue(assess_delivery(trace_fixture(), deepcopy(RECORD), EVENT, 0, True)["passed"])
        for mutate in (lambda rows: rows.clear(),
                       lambda rows: rows[1]["item"]["arguments"].update(event_id="other"),
                       lambda rows: rows[0]["item"].update(server="other"),
                       lambda rows: rows[0]["item"]["result"].update(isError=True),
                       lambda rows: rows.append({"type": "item.completed", "item": {"type": "command_execution"}})):
            rows = trace_fixture()
            mutate(rows)
            self.assertFalse(assess_delivery(rows, deepcopy(RECORD), EVENT, 0, True)["passed"])
        self.assertFalse(assess_delivery(trace_fixture(), deepcopy(RECORD), EVENT, 0, False)["passed"])
        self.assertFalse(assess_delivery(trace_fixture(), {"result": []}, EVENT, 0, True)["passed"])

    def test_real_queue_two_events_and_failure_before_ack_recovery_with_fake_cli(self):
        from eventguard.events.store import EventStore
        from eventguard.queue_inbox import QueueInbox
        from eventguard.synthetic import make_synthetic
        (self.source / "eventguard.sqlite3").unlink()
        store = EventStore(self.source)
        events = [make_synthetic("listener"), make_synthetic("coverage")]
        for event in events:
            store.enqueue(event)
        self.script.write_text(FAKE_QUEUE, encoding="utf-8")
        mode = ["fail"]
        original = subprocess.Popen

        def fake_command(codex, python, source, state, event_id, evidence, **kwargs):
            return [sys.executable, "-B", str(self.script), str(source), str(state), event_id,
                    mode[0], str(ROOT / "src")]

        def launch(*args, **kwargs):
            child = original(*args, **kwargs)
            self.children.append(child)
            return child

        with patch("eventguard.agent_dispatch.command", side_effect=fake_command), \
             patch("eventguard.agent_dispatch.shutil.which", return_value=sys.executable), \
             patch("eventguard.agent_dispatch.importlib.util.find_spec", return_value=True), \
             patch("eventguard.agent_dispatch.subprocess.Popen", side_effect=launch):
            self.assertEqual(self.invoke("queue-before-ack"), 1)
            backend = QueueInbox(self.source, self.state_dir)
            first = backend.pending_event_id()
            query_id = backend.evidence(first)["query_id"]
            self.assertFalse(backend.acknowledged(first))
            mode[0] = "success"
            self.assertEqual(self.invoke("queue-recovery"), 0)
            self.assertTrue(backend.acknowledged(first))
            self.assertEqual(backend.evidence(first)["query_id"], query_id)
            second = backend.pending_event_id()
            self.assertNotEqual(first, second)
            self.assertEqual(self.invoke("queue-second"), 0)
            self.assertTrue(backend.acknowledged(second))
            self.assertEqual(self.invoke("queue-empty", max_seconds=.03, poll_seconds=.01), 0)
            self.assertIsNone(backend.pending_event_id())
        self.assertEqual(set([first, second]), {event["event_id"] for event in events})
        self.assertEqual(len(self.children), 3, "Only explicit fake invocations; idle launches none")
        self.assertTrue(all(child.poll() == 0 for child in self.children), "Capture workers exited naturally")


if __name__ == "__main__":
    unittest.main()
