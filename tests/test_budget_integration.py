"""Cross-entry launch fixtures with owned Python fake CLI, never a model.

The application has no daily quota. The historical budget stays fenced: no
capture, acceptance or dispatch entry may read, initialize or change it.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

from budget_fixtures import isolated_launch
from eventguard import agent_budget, agent_dispatch, delivery_validation
from eventguard.acceptance_control import read_json, write_json
from eventguard.acceptance_process import capture, launch_hash
from eventguard.capture_receipt import validate_receipt
from eventguard.events.store import EventStore
from eventguard.processes import remaining_owned
from eventguard.queue_inbox import QueueInbox
from eventguard.synthetic import make_synthetic


ROOT = Path(__file__).resolve().parents[1]
FAKE = '''# Explicit synthetic fixture. This program is not a Codex agent.
import json,sys
from pathlib import Path
with Path(sys.argv[1]).open("a",encoding="utf-8") as marker:
 marker.write(json.dumps({"scope":"fake_cli_only","mode":sys.argv[2]})+"\\n")
sys.stdin.read()
if sys.argv[2]=="plain":
 print(json.dumps({"scope":"fake_cli_only"}),flush=True)
 raise SystemExit(0)
sys.path.insert(0,sys.argv[6])
from eventguard.queue_inbox import QueueInbox
backend=QueueInbox(sys.argv[3],sys.argv[4],event_id=sys.argv[5])
def reply(tool,args,value):
 print(json.dumps({"type":"item.completed","item":{"id":"fake-"+tool,"type":"mcp_tool_call","server":"eventguard_inbox","tool":tool,"status":"completed","error":None,"arguments":args,"result":{"content":[{"type":"text","text":json.dumps(value)}]}}}),flush=True)
item=backend.receive_event(); event=item["event_id"]; reply("receive_event",{},item)
query=backend.query_evidence(event); reply("query_evidence",{"event_id":event},query)
if sys.argv[2]=="fail":
 print(json.dumps({"type":"turn.failed"}),flush=True)
 raise SystemExit(7)
if sys.argv[2]!="read":
 args={"event_id":event,"query_id":query["query_id"],"decision":"reviewed_metadata"}
 reply("ack_event",args,backend.ack_event(**args))
print(json.dumps({"type":"turn.completed"}),flush=True)
'''


class NoQuotaAdmissionIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.fake = self.base / "synthetic_fake_cli.py"
        self.fake.write_text(FAKE, encoding="utf-8")
        self.marker = self.base / "fake-invocations.jsonl"
        self.before_owned = remaining_owned()
        self.evidence = {"scope": "synthetic_no_quota_integration_python_fake_cli_not_real_agent",
                         "capture_receipts": [], "model_calls": 0}
        self.enterContext(patch.dict(os.environ, {"PYTHONPATH": str(ROOT / "src")}))

    def tearDown(self):
        self.assertEqual(remaining_owned(), self.before_owned, "test must leave no owned process behind")
        self.evidence.update(remaining_owned_delta=remaining_owned() - self.before_owned,
                             fake_cli_invocations=len(self.invocations()))

    def fake_args(self, mode="plain", source=None, state=None, event=None):
        return [sys.executable, "-B", str(self.fake), str(self.marker), mode,
                str(source or self.base / "unused-source"), str(state or self.base / "unused-state"),
                event or "synthetic-unused", str(ROOT / "src")]

    def invocations(self):
        return [] if not self.marker.exists() else [json.loads(line) for line in self.marker.read_text(encoding="utf-8").splitlines()]

    def source(self, name, *, with_event=True):
        source = self.base / name
        store = EventStore(source)
        event = make_synthetic()
        if with_event:
            store.enqueue(event)
        return source, event

    def fake_entries(self, mode="ack"):
        context = ExitStack()
        def command(codex, python, source, state, event, evidence, *, allow_ack=True, **kwargs):
            self.assertEqual(Path(codex), Path(sys.executable))
            return self.fake_args("read" if not allow_ack else mode, source, state, event)
        for module in (agent_dispatch, delivery_validation):
            context.enter_context(patch.object(module, "command", side_effect=command))
            context.enter_context(patch.object(module.shutil, "which", return_value=sys.executable))
            context.enter_context(patch.object(module.importlib.util, "find_spec", return_value=True))
        return context

    def dispatch(self, name, source, state, **kwargs):
        return agent_dispatch.run(self.base / name, source, state, codex=sys.executable,
                                  max_tasks=1, max_seconds=kwargs.pop("max_seconds", 15),
                                  poll_seconds=.01, execute=kwargs.pop("execute", True), **kwargs)

    def assert_exit(self, directory, *, success=True):
        started, receipt = read_json(directory / "capture-start.json"), read_json(directory / "capture-exit.json")
        self.assertEqual(validate_receipt(receipt, started, started["attempt_id"], require_success=success), [])
        self.assertTrue(receipt["process"]["managed"])
        self.assertEqual(receipt["process"]["remaining_owned_processes"], 0)
        self.assertFalse(receipt["process"]["forcibly_terminated"])
        self.evidence["capture_receipts"].append(receipt)
        return receipt

    @unittest.skipUnless(os.name == "nt", "real Windows private Jobs + synthetic Python fake CLI")
    def test_missing_or_corrupt_historical_budget_is_never_read_by_launch_entries(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                root = self.base / ("corrupt" if corrupt else "missing")
                historical = root / "installation/authority.sqlite3"
                if corrupt:
                    historical.parent.mkdir(parents=True)
                    historical.write_bytes(b"corrupt synthetic historical budget")
                with isolated_launch(root / "launch"), self.fake_entries(), \
                        patch.object(agent_budget, "AUTHORITY_PATH", historical):
                    direct = root / "capture"; direct.mkdir(parents=True, exist_ok=True)
                    self.assertEqual(capture(self.fake_args(), direct, uuid.uuid4().hex, "synthetic only"), 0)
                    self.assert_exit(direct)
                    acceptance = root / "acceptance"
                    manifest = delivery_validation.prepare(acceptance, "single")
                    self.assertTrue(delivery_validation.execute(acceptance, manifest, sys.executable)["passed"])
                    self.assert_exit(acceptance / "stage-1")
                    source, event = self.source(root.name + "-source")
                    self.assertEqual(self.dispatch(root.name + "-dispatch", source, root / "state"), 0)
                    self.assertEqual(EventStore(source).get_event(event["event_id"])["delivery_status"], "ack")
                if corrupt:
                    self.assertEqual(historical.read_bytes(), b"corrupt synthetic historical budget")
                else:
                    self.assertFalse(historical.exists(), "a missing historical budget is never initialized")
        self.assertEqual(len(self.invocations()), 6)

    @unittest.skipUnless(os.name == "nt", "real Windows private Job + synthetic Python fake CLI")
    def test_completed_attempt_directory_never_launches_twice_even_with_changed_binding(self):
        with isolated_launch(self.base / "replay"):
            first = self.base / "capture-first"; first.mkdir()
            token, args, prompt = uuid.uuid4().hex, self.fake_args(), "synthetic fixture"
            self.assertEqual(capture(args, first, token, prompt), 0)
            self.assert_exit(first)
            names = ("capture-launch-intent.json", "capture-start.json", "capture-exit.json")
            before = {name: (first / name).read_bytes() for name in names}
            for mutation in ("same", "argv", "prompt"):
                requested = args + ["changed"] if mutation == "argv" else args
                incoming = prompt + " changed" if mutation == "prompt" else prompt
                with self.subTest(mutation=mutation), patch("eventguard.acceptance_process.spawn") as starter:
                    self.assertNotEqual(capture(requested, first, token, incoming), 0)
                    starter.assert_not_called()
            self.assertEqual({name: (first / name).read_bytes() for name in names}, before)
        self.assertEqual(len(self.invocations()), 1)

    @unittest.skipUnless(os.name == "nt", "real Windows private Jobs + synthetic Python fake CLI")
    def test_acceptance_dispatch_retry_and_direct_entries_have_no_five_task_cap(self):
        with isolated_launch(self.base / "mixed"):
            with self.fake_entries():
                root = self.base / "acceptance-one"
                manifest = delivery_validation.prepare(root, "single")
                self.assertTrue(delivery_validation.execute(root, manifest, sys.executable)["passed"])
                self.assert_exit(root / "stage-1")
            source, event = self.source("retry-source")
            state = self.base / "retry-state"
            with self.fake_entries("fail"):
                self.assertEqual(self.dispatch("dispatch-first-failed", source, state), 1)
            failed = agent_dispatch.status(self.base / "dispatch-first-failed")
            self.assert_exit(self.base / "dispatch-first-failed/attempts" / failed["active_attempt_id"], success=False)
            self.assertEqual(EventStore(source).get_event(event["event_id"])["delivery_status"], "pending")
            with self.fake_entries():
                self.assertEqual(self.dispatch("dispatch-retry", source, state), 0)
            retried = agent_dispatch.status(self.base / "dispatch-retry")
            retry_dir = self.base / "dispatch-retry/attempts" / retried["active_attempt_id"]
            self.assert_exit(retry_dir)
            for saved in (failed, retried):
                self.assertEqual(saved["supervisor_process"]["remaining_owned_processes"], 0)
                self.assertFalse(saved["supervisor_process"]["forcibly_terminated"])
            # The explicit retry still uses this event's durable attempt slots.
            records = read_json(state / "dispatcher-attempts.json")["events"][event["event_id"]]
            self.assertEqual([record.get("passed") for record in records], [False, True])
            direct = self.base / "direct-four"; direct.mkdir()
            self.assertEqual(capture(self.fake_args(), direct, uuid.uuid4().hex, "synthetic direct capture"), 0)
            self.assert_exit(direct)
            with self.fake_entries():
                root = self.base / "acceptance-five"
                manifest = delivery_validation.prepare(root, "single")
                self.assertTrue(delivery_validation.execute(root, manifest, sys.executable)["passed"])
                self.assert_exit(root / "stage-1")
                other_source, other_event = self.source("six-new-source")
                self.assertEqual(self.dispatch("six-new-run", other_source, self.base / "six-new-state"), 0)
            sixth = agent_dispatch.status(self.base / "six-new-run")
            self.assertEqual(sixth["state"], "task_limit_reached")
            self.assertNotIn("budget", sixth)
            self.assert_exit(self.base / "six-new-run/attempts" / sixth["active_attempt_id"])
            self.assertEqual(EventStore(other_source).get_event(other_event["event_id"])["delivery_status"], "ack")
        self.assertEqual(len(self.invocations()), 6)

    def test_unconfirmed_capture_intent_blocks_same_ledger_without_spawn(self):
        # Fabricated records only: the intent exists, but no start or exit
        # receipt proves what happened to OS creation. No process is created.
        source, event = self.source("unknown-source")
        state = self.base / "unknown-state"
        run_dir, token, run_id = self.base / "unknown-prior-run", uuid.uuid4().hex, uuid.uuid4().hex
        attempt = run_dir / "attempts" / token
        attempt.mkdir(parents=True)
        QueueInbox(source, state)  # The dedicated inbox the prior run would have created.
        write_json(run_dir / "dispatch.json", {"kind": agent_dispatch.KIND, "run_id": run_id})
        write_json(run_dir / "status.json", {"kind": agent_dispatch.KIND, "run_id": run_id, "state": "running",
                                             "active_attempt_id": token, "child_exited": False})
        write_json(attempt / "capture-launch-intent.json", {
            "kind": "eventguard-capture-launch-intent-v1", "attempt_id": token,
            "launch_hash": launch_hash(self.fake_args(), agent_dispatch.PROMPT), "at": 0,
            "application_quota": "not_used"})
        ledger = state / "dispatcher-attempts.json"
        write_json(ledger, {"kind": agent_dispatch.KIND, "events": {event["event_id"]: [{
            "event_id": event["event_id"], "attempt_id": token, "run_id": run_id,
            "run_dir": str(run_dir), "state": "started"}]}})
        before = ledger.read_bytes()
        with isolated_launch(self.base / "unknown") as launch, self.fake_entries(), \
                patch.object(agent_dispatch, "spawn", side_effect=AssertionError("No worker permitted")) as starter:
            for name in ("unknown-run-one", "unknown-run-two"):
                with self.subTest(run=name):
                    self.assertEqual(self.dispatch(name, source, state), 3)
                    saved = agent_dispatch.status(self.base / name)
                    self.assertEqual(saved["reason"], "prior_child_exit_unconfirmed")
                    self.assertEqual(ledger.read_bytes(), before)
                    self.assertEqual(EventStore(source).get_event(event["event_id"])["delivery_status"], "pending")
            starter.assert_not_called()
            self.assertFalse(launch.gate_entered())
        self.assertEqual(self.invocations(), [])

    def test_prepare_and_idle_or_preflight_dispatch_never_enter_launch_gate_or_start_workers(self):
        with isolated_launch(self.base / "idle") as launch:
            with patch.object(delivery_validation, "capture") as capture_start:
                for case in delivery_validation.COUNTS:
                    delivery_validation.prepare(self.base / ("prepared-" + case), case)
                capture_start.assert_not_called()
            source, _ = self.source("idle-source", with_event=False)
            with self.fake_entries(), patch.object(agent_dispatch, "spawn") as starter:
                self.assertEqual(self.dispatch("preflight-no-execute", source, self.base / "idle-state", execute=False), 0)
                self.assertEqual(self.dispatch("idle-no-event", source, self.base / "idle-state", max_seconds=.08), 0)
                starter.assert_not_called()
            self.assertFalse(launch.gate_entered())
        self.assertEqual(self.invocations(), [])


if __name__ == "__main__":
    unittest.main()
