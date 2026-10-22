"""Cross-entry admission fixtures with owned Python fake CLI, never a model."""
from contextlib import closing, ExitStack
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

from budget_fixtures import isolated_budget, reserve_capture
from eventguard import agent_budget, agent_dispatch, delivery_validation
from eventguard.acceptance_control import read_json
from eventguard.acceptance_process import capture, launch_hash
from eventguard.agent_budget import BudgetAuthority
from eventguard.capture_receipt import validate_receipt
from eventguard.events.store import EventStore
from eventguard.processes import remaining_owned
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


class BudgetAdmissionIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.fake = self.base / "synthetic_fake_cli.py"
        self.fake.write_text(FAKE, encoding="utf-8")
        self.marker = self.base / "fake-invocations.jsonl"
        self.before_owned = remaining_owned()
        self.evidence = {"scope": "synthetic_budget_integration_python_fake_cli_not_real_agent",
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

    def assert_no_start(self, directory):
        self.assertFalse((directory / "capture-start.json").exists())
        self.assertFalse((directory / "capture-exit.json").exists())

    def test_default_missing_or_corrupt_authority_refuses_all_launch_entries(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                root = self.base / ("corrupt" if corrupt else "missing")
                authority_path = root / "installation/authority.sqlite3"
                if corrupt:
                    authority = BudgetAuthority(authority_path)
                    authority.initialize(known_used=0)
                    authority_path.write_bytes(b"corrupt synthetic authority")
                with patch.object(agent_budget, "AUTHORITY_PATH", authority_path), self.fake_entries(), \
                        patch("eventguard.acceptance_process.spawn") as capture_spawn, \
                        patch.object(agent_dispatch, "spawn") as dispatcher_spawn:
                    direct = root / "capture"; direct.mkdir(parents=True)
                    self.assertEqual(capture(self.fake_args(), direct, uuid.uuid4().hex, "synthetic only"), 2)
                    self.assert_no_start(direct)
                    acceptance = root / "acceptance"
                    manifest = delivery_validation.prepare(acceptance, "single")
                    with self.assertRaises(agent_budget.BudgetError):
                        delivery_validation.execute(acceptance, manifest, sys.executable)
                    self.assertEqual(EventStore(acceptance / "source").get_event(manifest["events"][0]["event_id"])["delivery_status"], "pending")
                    source, event = self.source(root.name + "-source")
                    self.assertEqual(self.dispatch(root.name + "-dispatch", source, root / "state"), 1)
                    self.assertEqual(agent_dispatch.status(self.base / (root.name + "-dispatch"))["reason"], "budget_unavailable")
                    self.assertEqual(EventStore(source).get_event(event["event_id"])["delivery_status"], "pending")
                    capture_spawn.assert_not_called()
                    dispatcher_spawn.assert_not_called()
                if not corrupt:
                    self.assertFalse(authority_path.exists(), "a missing authority is never implicitly initialized")
        self.assertEqual(self.invocations(), [])

    def test_capture_requires_ticket_and_bound_argv_prompt_before_spawn(self):
        for mutation in ("no-ticket", "argv", "prompt"):
            with self.subTest(mutation=mutation), isolated_budget(self.base / mutation) as authority:
                directory = self.base / (mutation + "-capture"); directory.mkdir()
                token, args, prompt = uuid.uuid4().hex, self.fake_args(), "synthetic fixture prompt"
                if mutation != "no-ticket":
                    reserve_capture(authority, args, directory, token, prompt)
                requested = args + ["changed"] if mutation == "argv" else args
                incoming = prompt + " changed" if mutation == "prompt" else prompt
                with patch("eventguard.acceptance_process.spawn") as starter:
                    self.assertEqual(capture(requested, directory, token, incoming), 2)
                    starter.assert_not_called()
                self.assert_no_start(directory)
                self.assertEqual(authority.status()["used"], 0 if mutation == "no-ticket" else 1)
        self.assertEqual(self.invocations(), [])

    @unittest.skipUnless(os.name == "nt", "real Windows private Job + synthetic Python fake CLI")
    def test_completed_capture_ticket_cannot_launch_twice(self):
        with isolated_budget(self.base / "replay") as authority:
            first, replay = self.base / "capture-first", self.base / "capture-replay"
            first.mkdir(); replay.mkdir()
            token, args, prompt = uuid.uuid4().hex, self.fake_args(), "synthetic fixture"
            reserve_capture(authority, args, first, token, prompt)
            self.assertEqual(capture(args, first, token, prompt), 0)
            self.assert_exit(first)
            with patch("eventguard.acceptance_process.spawn") as starter:
                self.assertEqual(capture(args, replay, token, prompt), 2)
                starter.assert_not_called()
            self.assert_no_start(replay)
            self.assertEqual(authority.status()["used"], 1)
            self.assertEqual(authority.admission(token)["state"], "completed")
        self.assertEqual(len(self.invocations()), 1)

    @unittest.skipUnless(os.name == "nt", "real Windows private Jobs + synthetic Python fake CLI")
    def test_acceptance_dispatch_retry_share_five_admissions_across_directories(self):
        with isolated_budget(self.base / "mixed") as authority:
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
            direct = self.base / "direct-four"; direct.mkdir()
            token, args, prompt = uuid.uuid4().hex, self.fake_args(), "synthetic direct capture"
            reserve_capture(authority, args, direct, token, prompt)
            self.assertEqual(capture(args, direct, token, prompt), 0)
            self.assert_exit(direct)
            with self.fake_entries():
                root = self.base / "acceptance-five"
                manifest = delivery_validation.prepare(root, "single")
                self.assertTrue(delivery_validation.execute(root, manifest, sys.executable)["passed"])
                self.assert_exit(root / "stage-1")
                other_source, other_event = self.source("six-new-source")
                with patch.object(agent_dispatch, "spawn") as starter:
                    self.assertEqual(self.dispatch("six-new-run", other_source, self.base / "six-new-state"), 1)
                    starter.assert_not_called()
                self.assertEqual(agent_dispatch.status(self.base / "six-new-run")["reason"], "budget_exhausted")
                self.assertEqual(EventStore(other_source).get_event(other_event["event_id"])["delivery_status"], "pending")
            self.assertEqual(authority.status()["used"], 5)
            self.assertIsNone(authority.status()["active"])
            with closing(sqlite3.connect(authority.path.as_uri() + "?mode=ro", uri=True)) as db:
                self.assertEqual(dict(db.execute("SELECT kind,COUNT(*) FROM admissions GROUP BY kind")),
                                 {"acceptance": 3, "dispatch": 1, "retry": 1})
        self.assertEqual(len(self.invocations()), 5)

    def test_unconfirmed_launch_blocks_other_source_and_next_day_without_spawn(self):
        with isolated_budget(self.base / "unknown-exit") as authority:
            now = datetime.now(timezone.utc)
            authority.clock = lambda: now
            token, args, prompt = uuid.uuid4().hex, self.fake_args(), "synthetic unstarted launch intent"
            reserve_capture(authority, args, self.base, token, prompt)
            authority.begin_launch(token, launch_hash=launch_hash(args, prompt))
            for day in (0, 1):
                with self.subTest(day=day):
                    now = now + timedelta(days=day)
                    source, event = self.source("unknown-source-" + str(day))
                    with self.fake_entries(), patch.object(agent_dispatch, "spawn") as starter:
                        self.assertEqual(self.dispatch("unknown-run-" + str(day), source, self.base / ("unknown-state-" + str(day))), 1)
                        starter.assert_not_called()
                    saved = agent_dispatch.status(self.base / ("unknown-run-" + str(day)))
                    self.assertEqual(saved["reason"], "budget_child_exit_unconfirmed")
                    self.assertEqual(authority.status()["active"]["attempt_id"], token)
                    self.assertEqual(EventStore(source).get_event(event["event_id"])["delivery_status"], "pending")
                    root = self.base / ("unknown-acceptance-" + str(day))
                    manifest = delivery_validation.prepare(root, "single")
                    with self.fake_entries(), patch.object(delivery_validation, "capture") as starter:
                        with self.assertRaisesRegex(agent_budget.BudgetError, "budget_child_exit_unconfirmed"):
                            delivery_validation.execute(root, manifest, sys.executable)
                        starter.assert_not_called()
        self.assertEqual(self.invocations(), [])

    def test_prepare_and_idle_or_preflight_dispatch_do_not_charge_or_start_workers(self):
        with isolated_budget(self.base / "idle") as authority:
            with patch.object(delivery_validation, "capture") as capture_start:
                for case in delivery_validation.COUNTS:
                    delivery_validation.prepare(self.base / ("prepared-" + case), case)
                capture_start.assert_not_called()
            source, _ = self.source("idle-source", with_event=False)
            with self.fake_entries(), patch.object(agent_dispatch, "spawn") as starter, \
                    patch.object(agent_dispatch, "open_authority") as opener:
                self.assertEqual(self.dispatch("preflight-no-execute", source, self.base / "idle-state", execute=False), 0)
                self.assertEqual(self.dispatch("idle-no-event", source, self.base / "idle-state", max_seconds=.08), 0)
                opener.assert_not_called()
                starter.assert_not_called()
            self.assertEqual(authority.status()["used"], 0)
            self.assertIsNone(authority.status()["active"])
        self.assertEqual(self.invocations(), [])


if __name__ == "__main__":
    unittest.main()
