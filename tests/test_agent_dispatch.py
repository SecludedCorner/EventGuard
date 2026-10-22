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


FAKE = """import json,sys,time
rows=json.load(open(sys.argv[1],encoding='utf-8'))
mode=sys.argv[2]
if mode=='slow': time.sleep(4)
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
                   max_seconds=kwargs.pop("max_seconds", 5), execute=kwargs.pop("execute", True), **kwargs)

    def test_scoped_command_and_prompt_no_preloaded_event(self):
        args = command("codex.exe", Path("C:/Python313/python.exe"), self.source, self.state_dir,
                       EVENT, self.directory, allow_live=True)
        server = tomllib.loads(next(arg for arg in args if arg.startswith("mcp_servers.")))["mcp_servers"]["eventguard_inbox"]
        self.assertEqual(server["enabled_tools"], list(TOOLS))
        self.assertEqual(server["tools"], {tool: {"approval_mode": "approve"} for tool in TOOLS})
        self.assertIn("--allow-live", server["args"])
        self.assertIn("features.shell_tool=false", args)
        self.assertIn("features.unbounded_connection_retries=false", args)
        self.assertNotIn(EVENT, PROMPT)
        self.assertFalse(any("bypass" in arg for arg in args))

    def test_no_execute_and_no_event_make_zero_cli_calls(self):
        with self.fixtures():
            self.assertEqual(self.invoke("preflight", execute=False), 0)
            self.backend.pending = None
            self.assertEqual(self.invoke("idle", max_seconds=.08, poll_seconds=.01), 0)
        self.assertEqual(self.children, [])
        self.assertEqual(status(self.directory / "preflight")["state"], "preflight_ready")
        self.assertEqual(status(self.directory / "idle")["state"], "time_limit_reached")

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
        with self.fixtures("slow"):
            self.assertEqual(self.invoke("pending", max_seconds=3), 3)
            self.assertEqual(self.invoke("refused"), 3)
        self.assertEqual(len(self.children), 1)
        self.assertEqual(status(self.directory / "refused")["reason"], "prior_child_exit_unconfirmed")
        self.children[0].wait(timeout=5)
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
        with self.fixtures():
            self.assertEqual(self.invoke("bind", max_seconds=.3, poll_seconds=.01), 0)
            self.assertEqual(run(self.directory / "alternate", self.source, self.directory / "other-state",
                                 execute=True, max_seconds=.3), 2)
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
